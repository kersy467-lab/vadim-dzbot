"""Creator bankruptcy transfers real assets into the state and auction markets."""

import asyncio
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
from backend.db.session import get_db_session
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.bankruptcy_market import NatBankruptcyMarketLot
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.creator import (
    NatBondListing, NatCreatorAuditLog, NatStateBond, NatStateBondHolding, NatStateTreasury,
)
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.npc import NatNpcDailyVolume
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.services.forced_bankruptcy_service import ForcedBankruptcyService
from backend.natbirzha.services.bankruptcy_market_service import BankruptcyMarketService
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user


@pytest.mark.parametrize(
    ("asset_count", "expected_seized"),
    [(1, 1), (2, 1), (3, 2), (4, 3), (5, 4), (6, 4), (7, 5)],
)
def test_seize_count_rounds_seventy_percent_to_nearest_asset(
    asset_count: int, expected_seized: int,
) -> None:
    assert BankruptcyMarketService._seize_count(asset_count) == expected_seized


def test_admin_bankruptcy_liquidates_and_lists_seized_assets_once() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            bankrupt = NatCompany(
                user_id=820_001, name="Water Corp", specialization="water", cash=10_000,
            )
            buyer = NatCompany(user_id=820_002, name="Tech Buyer", specialization="technoprom", cash=500_000)
            issuer = NatCompany(user_id=820_003, name="Share Issuer", specialization="miner", cash=100_000)
            treasury = NatStateTreasury(id=1, cash=5_000_000)
            session.add_all([bankrupt, buyer, issuer, treasury])
            await session.flush()

            factories = [NatFactory(
                company_id=bankrupt.id, building_type="grain_farm", specialization="agrarian", level=1,
            ) for _ in range(2)]
            businesses = [NatBusiness(
                company_id=bankrupt.id, business_type="coal_open_pit", specialization="miner", stage=stage,
                status="ACTIVE", capital_invested=100_000 * stage,
                base_income_per_hour=0, base_maintenance_per_hour=12,
            ) for stage in (1, 2)]
            session.add_all(factories + businesses)
            inventory = NatInventory(
                company_id=bankrupt.id, item_id="water", quantity=100, reserved_quantity=0, avg_cost_basis=2,
            )
            session.add(inventory)
            stock = NatStock(
                company_id=issuer.id, total_shares=10_000, founder_shares=6_000,
                float_shares=4_000, current_price=50, last_valuation=500_000, is_listed=True,
            )
            session.add(stock)
            await session.flush()
            stock_holding = NatStockHolding(
                stock_id=stock.id, holder_company_id=bankrupt.id, shares_count=100, avg_price=45,
            )
            bond = NatStateBond(
                title="Госзаём", total_volume=10, remaining_volume=2, face_value=100,
                coupon_rate=7.5, maturity_days=30, coupon_interval_days=1,
                purpose="test", actor_id=1, is_active=True, status="ACTIVE",
                next_coupon_at=get_game_now() + timedelta(hours=1),
                maturity_at=get_game_now() + timedelta(days=30),
            )
            session.add_all([stock_holding, bond])
            await session.flush()
            bond_holding = NatStateBondHolding(
                bond_id=bond.id, company_id=bankrupt.id, quantity=5, reserved_quantity=1, invested_cash=500,
            )
            bond_listing = NatBondListing(
                operation_key="bankrupt-bond-listing", bond_id=bond.id, seller_company_id=bankrupt.id,
                quantity=1, unit_price=100, status="OPEN",
            )
            session.add_all([bond_holding, bond_listing])
            buy_order = NatMarketOrder(
                company_id=buyer.id, order_type="BUY", item_id="water", price=10,
                quantity=10, remaining_qty=10, status="ACTIVE",
            )
            buyer.cash -= 100
            session.add(buy_order)
            await session.commit()

            before_treasury = treasury.cash
            response = await ForcedBankruptcyService.execute(
                session, company_id=bankrupt.id, actor_id=777,
                operation_key="creator-bankruptcy-water-corp-1",
            )
            await session.refresh(bankrupt)
            await session.refresh(treasury)
            await session.refresh(inventory)
            await session.refresh(stock_holding)
            await session.refresh(bond_holding)
            await session.refresh(bond)
            await session.refresh(bond_listing)

            lots = (await session.execute(select(NatBankruptcyMarketLot))).scalars().all()
            active_lots = [lot for lot in lots if lot.status == "ACTIVE"]
            factory_lot = next(lot for lot in active_lots if lot.asset_kind == "FACTORY")
            business_lot = next(lot for lot in active_lots if lot.asset_kind == "BUSINESS")
            assert bankrupt.is_bankrupt is True
            assert bankrupt.cash == 0
            assert treasury.cash == before_treasury + 10_000 + 100
            assert len(active_lots) == 3, [(lot.asset_kind, lot.status, lot.quantity) for lot in lots]
            assert all(
                lot.ask_price >= lot.cost_basis * 1.3
                for lot in active_lots if lot.asset_kind != "STOCK"
            )
            assert inventory.quantity == 30  # 70% is offered; 60 units without bids disappear
            assert stock_holding.shares_count == 0
            assert bond_holding.quantity == 0 and bond_holding.reserved_quantity == 0
            assert bond.remaining_volume == 7 and bond_listing.status == "CANCELLED"
            assert buy_order.status == "FILLED" and buy_order.remaining_qty == 0
            assert await session.scalar(select(func.count()).select_from(NatMarketTrade)) == 1
            audit = await session.scalar(select(NatCreatorAuditLog).where(
                NatCreatorAuditLog.action == "CREATOR_BANKRUPTCY_LIQUIDATION"
            ))
            assert audit is not None and audit.target_id == str(bankrupt.id)
            frozen_factory = await session.get(NatFactory, factory_lot.asset_id)
            frozen_business = await session.get(NatBusiness, business_lot.asset_id)
            assert frozen_factory is not None and frozen_factory.is_active is False
            assert frozen_business is not None and frozen_business.status == "BANKRUPT"

            # An unrelated industry can buy the confiscated plant, with the premium going to Treasury.
            purchased = await BankruptcyMarketService.purchase_lot(
                session, company_id=buyer.id, lot_id=factory_lot.id, commit=False,
            )
            assert purchased["success"] is True
            assert purchased["cross_industry"] is True
            factory = await session.get(NatFactory, factory_lot.asset_id)
            assert factory is not None and factory.company_id == buyer.id
            assert factory.is_active is True
            assert factory.bankruptcy_acquired is True
            assert ProductionTickEngine.get_effective_efficiency(buyer, factory) == 1.0
            business_purchase = await BankruptcyMarketService.purchase_lot(
                session, company_id=buyer.id, lot_id=business_lot.id, commit=False,
            )
            bought_business = await session.get(NatBusiness, business_lot.asset_id)
            assert business_purchase["success"] is True
            assert bought_business is not None and bought_business.company_id == buyer.id
            assert bought_business.status == "ACTIVE"
            await session.refresh(treasury)
            assert treasury.cash == before_treasury + 10_000 + 100 + factory_lot.ask_price + business_lot.ask_price

            stock_lot = next(lot for lot in active_lots if lot.asset_kind == "STOCK")
            stock_purchase = await BankruptcyMarketService.purchase_lot(
                session, company_id=buyer.id, lot_id=stock_lot.id, commit=False,
            )
            buyer_stock = await session.scalar(select(NatStockHolding).where(
                NatStockHolding.stock_id == stock.id,
                NatStockHolding.holder_company_id == buyer.id,
            ))
            assert stock_purchase["success"] is True
            assert buyer_stock is not None and buyer_stock.shares_count == 100
            await session.refresh(treasury)
            assert treasury.cash == before_treasury + 10_000 + 100 + factory_lot.ask_price + business_lot.ask_price + stock_lot.ask_price

            replay = await ForcedBankruptcyService.execute(
                session, company_id=bankrupt.id, actor_id=777,
                operation_key="creator-bankruptcy-water-corp-1",
            )
            assert replay["success"] is True
            assert await session.scalar(select(func.count()).select_from(NatNpcDailyVolume)) == 0

            stale_lot = NatBankruptcyMarketLot(
                operation_key="missing-market-asset", former_company_id=bankrupt.id,
                former_company_name=bankrupt.name, asset_kind="FACTORY", asset_id=999_999,
                asset_type="mine", title="Missing mine", industry="miner", asset_level=1,
                cost_basis=100, ask_price=130, status="ACTIVE",
            )
            session.add(stale_lot)
            await session.flush()
            stale_purchase = await BankruptcyMarketService.purchase_lot(
                session, company_id=buyer.id, lot_id=stale_lot.id, commit=False,
            )
            await session.refresh(stale_lot)
            assert stale_purchase["reason"] == "stale_asset"
            assert stale_lot.status == "CANCELLED"

        await engine.dispose()

    asyncio.run(check())


def test_bankruptcy_market_api_liquidates_lists_and_buys_factory() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            creator = User(tg_id=820_020, full_name="Market Creator", role="admin")
            bankrupt_user = User(tg_id=820_021, full_name="Market Debtor")
            buyer_user = User(tg_id=820_022, full_name="Market Buyer")
            session.add_all([creator, bankrupt_user, buyer_user])
            await session.flush()
            bankrupt = NatCompany(
                user_id=bankrupt_user.id, name="API Bankrupt Co", specialization="agrarian", cash=10_000,
            )
            buyer = NatCompany(
                user_id=buyer_user.id, name="API Asset Buyer", specialization="miner", cash=1_000_000,
            )
            treasury = NatStateTreasury(id=1, cash=50_000)
            session.add_all([bankrupt, buyer, treasury])
            await session.flush()
            factories = [NatFactory(
                company_id=bankrupt.id, building_type="grain_farm", specialization="agrarian", level=1,
            ) for _ in range(4)]
            session.add_all(factories)
            await session.commit()
            creator_user_id = creator.id
            buyer_user_id = buyer_user.id
            bankrupt_company_id = bankrupt.id
            buyer_company_id = buyer.id
            initial_treasury_cash = treasury.cash

        app = FastAPI()
        app.include_router(natbirzha_router, prefix="/api")

        async def test_session():
            async with sessions() as session:
                yield session

        async def test_user(
            x_test_user: int | None = Header(None, alias="X-Test-User"),
            session=Depends(get_db_session),
        ) -> User:
            if x_test_user is None:
                raise HTTPException(status_code=401, detail="Missing test identity")
            user = await session.get(User, x_test_user)
            if user is None:
                raise HTTPException(status_code=401, detail="Unknown test identity")
            return user

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_strict_natbirzha_user] = test_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            creator_headers = {
                "X-Test-User": str(creator_user_id),
                "Idempotency-Key": "api-bankruptcy-1",
            }
            liquidated = await client.post(
                f"/api/natbirzha/creator/players/{bankrupt_company_id}/bankruptcy",
                headers=creator_headers,
            )
            assert liquidated.status_code == 200, liquidated.text

            listing = await client.get("/api/natbirzha/bankruptcy-market")
            assert listing.status_code == 200, listing.text
            lots = listing.json()["lots"]
            assert len(lots) == 3
            lot = next(row for row in lots if row["asset_kind"] == "FACTORY")

            buyer_headers = {
                "X-Test-User": str(buyer_user_id),
                "Idempotency-Key": "api-bankruptcy-buy-1",
            }
            purchase_url = f"/api/natbirzha/bankruptcy-market/lots/{lot['id']}/buy"
            purchase = await client.post(purchase_url, headers=buyer_headers)
            replay = await client.post(purchase_url, headers=buyer_headers)
            assert purchase.status_code == 200, purchase.text
            assert replay.json() == purchase.json()

        async with sessions() as session:
            factory = (await session.execute(
                select(NatFactory).where(NatFactory.company_id == buyer_company_id)
            )).scalars().one()
            sold_lot = await session.get(NatBankruptcyMarketLot, lot["id"])
            buyer = await session.get(NatCompany, buyer_company_id)
            treasury = await session.get(NatStateTreasury, 1)
            assert factory.bankruptcy_acquired is True and factory.is_active is True
            assert sold_lot is not None and sold_lot.status == "SOLD"
            assert sold_lot.buyer_company_id == buyer_company_id
            assert buyer is not None and round(1_000_000 - buyer.cash, 2) == purchase.json()["paid"]
            assert treasury is not None
            assert round(treasury.cash - initial_treasury_cash - 10_000, 2) == purchase.json()["paid"]

        await engine.dispose()

    asyncio.run(check())


def test_company_reset_cancels_bankruptcy_lots_with_removed_assets() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            former_owner_user = User(tg_id=820_010, full_name="Former Owner")
            issuer_user = User(tg_id=820_011, full_name="Issuer")
            session.add_all([former_owner_user, issuer_user])
            await session.flush()
            former_owner = NatCompany(
                user_id=former_owner_user.id, name="Former Owner Co", specialization="miner",
            )
            issuer = NatCompany(user_id=issuer_user.id, name="Issuer Co", specialization="miner")
            session.add_all([former_owner, issuer])
            await session.flush()
            factory = NatFactory(
                company_id=former_owner.id, building_type="mine", specialization="miner",
            )
            stock = NatStock(company_id=issuer.id, current_price=20, is_listed=True)
            session.add_all([factory, stock])
            await session.flush()
            lots = [
                NatBankruptcyMarketLot(
                    operation_key="reset-former-owner", former_company_id=former_owner.id,
                    former_company_name=former_owner.name, asset_kind="FACTORY", asset_id=factory.id,
                    asset_type="mine", title="Mine", industry="miner", asset_level=1,
                    cost_basis=100, ask_price=130, status="ACTIVE",
                ),
                NatBankruptcyMarketLot(
                    operation_key="reset-stock-issuer", former_company_id=former_owner.id,
                    former_company_name=former_owner.name, asset_kind="STOCK", asset_id=stock.id,
                    asset_type="company_stock", title="Issuer stock", industry="miner",
                    asset_level=1, quantity=10, cost_basis=200, ask_price=200, status="ACTIVE",
                ),
            ]
            session.add_all(lots)
            await session.flush()
            await CompanyService.reset_company_for_user(session, issuer_user.id, commit=False)
            await session.refresh(lots[0])
            await session.refresh(lots[1])
            assert lots[0].status == "ACTIVE"  # The former owner remains intact.
            assert lots[1].status == "CANCELLED"  # The stock issuer was reset.

            await CompanyService.reset_company_for_user(session, former_owner_user.id, commit=False)
            await session.refresh(lots[0])
            assert lots[0].status == "CANCELLED"

        await engine.dispose()

    asyncio.run(check())


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", __file__]))
