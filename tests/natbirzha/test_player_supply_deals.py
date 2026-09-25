"""Lifecycle, limits and lazy settlement coverage for bilateral supply deals."""

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder
from backend.natbirzha.models.player_deals import NatSupplyDeal, NatSupplyDealSettlement
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.supply_deal_service import SupplyDealService
from backend.natbirzha.api.supply_deal_routes import router as supply_deal_router
from backend.natbirzha.services.auth_service import get_current_company
from backend.db.session import get_db_session


async def _fixture(database_url: str = "sqlite+aiosqlite:///:memory:"):
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session = sessions()
    users = [
        User(tg_id=991301, full_name="Buyer"),
        User(tg_id=991302, full_name="Supplier"),
    ]
    session.add_all(users)
    await session.flush()
    buyer = NatCompany(user_id=users[0].id, name="Buyer Co", specialization="agrarian", cash=100_000)
    supplier = NatCompany(user_id=users[1].id, name="Power Co", specialization="power_engineer", cash=10_000)
    session.add_all([buyer, supplier])
    await session.flush()
    session.add(NatBusiness(
        company_id=supplier.id, business_type="wind_park_v2", specialization="power_engineer",
        stage=1, status="ACTIVE", last_settled_at=get_game_now(),
    ))
    await session.flush()
    return engine, session, buyer, supplier


async def _lifecycle_and_limits() -> None:
    engine, session, buyer, supplier = await _fixture()
    now = get_game_now().replace(microsecond=0)
    try:
        available = await SupplyDealService.available_companies(
            session, buyer.id, current_user_id=buyer.user_id,
        )
        assert buyer.id not in {row["company_id"] for row in available}
        try:
            await SupplyDealService.create_offer(
                session, buyer, supplier_company_id=buyer.id, item_id="energy",
                quantity_per_hour=1, discount_pct=0, term_seconds=600,
                reward_type="PROFIT_SHARE", profit_share_pct=1, now=now,
            )
            raise AssertionError("Companies owned by the same player must not contract")
        except ValueError as exc:
            assert "своей компанией" in str(exc).lower()

        session.add(NatMarketOrder(
            company_id=supplier.id, order_type="SELL", item_id="energy", price=20,
            quantity=10, remaining_qty=10, status="ACTIVE",
        ))
        await session.flush()
        offer = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=100, discount_pct=20, term_seconds=600,
            reward_type="PROFIT_SHARE", profit_share_pct=45, now=now,
        )
        assert offer.status == "PENDING"
        assert offer.quoted_reference_price == 20
        preview = await SupplyDealService.serialize(session, offer, buyer.id, now=now)
        assert preview["unit_price"] == 16
        accepted = await SupplyDealService.accept(session, supplier, offer.id, now=now)
        assert accepted.status == "ACTIVE"
        assert accepted.starts_at == now
        assert accepted.expires_at == now + timedelta(minutes=10)
        try:
            await SupplyDealService.accept(session, supplier, offer.id, now=now)
            raise AssertionError("A deal must not be accepted twice")
        except ValueError:
            pass

        over_limit = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=1, discount_pct=0, term_seconds=600,
            reward_type="PROFIT_SHARE", profit_share_pct=10, now=now,
        )
        try:
            await SupplyDealService.accept(session, supplier, over_limit.id, now=now)
            raise AssertionError("Overlapping profit shares must be capped at 50%")
        except ValueError as exc:
            assert "50%" in str(exc)
        assert over_limit.status == "PENDING"
        await SupplyDealService.reject(session, supplier, over_limit.id, now=now)
        assert over_limit.status == "REJECTED"

        cancelled = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=1, discount_pct=0, term_seconds=600,
            reward_type="PROFIT_SHARE", profit_share_pct=1, now=now,
        )
        await SupplyDealService.cancel(session, buyer, cancelled.id, now=now)
        assert cancelled.status == "CANCELLED"

        try:
            await SupplyDealService.create_offer(
                session, buyer, supplier_company_id=supplier.id, item_id="energy",
                quantity_per_hour=1, discount_pct=51, term_seconds=600,
                reward_type="PROFIT_SHARE", profit_share_pct=1, now=now,
            )
            raise AssertionError("Discount above the server limit must be rejected")
        except ValueError:
            pass

        await SupplyDealService.advance_buyer_cursor(
            session, buyer.id, through=now + timedelta(minutes=11)
        )
        expired_count = await SupplyDealService.settle_expired(
            session, buyer.id, now=now + timedelta(minutes=11)
        )
        assert expired_count == 1
        assert accepted.status == "COMPLETED"
        await session.commit()
    finally:
        await session.close()
        await engine.dispose()


async def _fixed_payout_is_atomic() -> None:
    engine, session, buyer, supplier = await _fixture()
    now = get_game_now().replace(microsecond=0)
    try:
        buyer.cash = 25
        offer = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=10, discount_pct=0, term_seconds=1800,
            reward_type="FIXED_CASH", fixed_cash=100, now=now,
        )
        before_supplier_cash = supplier.cash
        try:
            await SupplyDealService.accept(session, supplier, offer.id, now=now)
            raise AssertionError("Acceptance must fail when buyer cannot pay")
        except ValueError as exc:
            assert "недостаточно" in str(exc).lower()
        assert buyer.cash == 25
        assert supplier.cash == before_supplier_cash
        assert offer.status == "PENDING"
        try:
            await SupplyDealService.create_offer(
                session, buyer, supplier_company_id=supplier.id, item_id="energy",
                quantity_per_hour=1, discount_pct=0, term_seconds=600,
                reward_type="FIXED_CASH", fixed_cash=float("nan"), now=now,
            )
            raise AssertionError("A non-finite one-time payout must be rejected")
        except ValueError:
            pass

        buyer.cash = 250
        accepted = await SupplyDealService.accept(session, supplier, offer.id, now=now)
        assert accepted.status == "ACTIVE"
        assert buyer.cash == 150
        assert supplier.cash == before_supplier_cash + 100
        assert accepted.fixed_cash_paid == 100
        assert len(accepted.__dict__) > 0
        deal_id = accepted.id
        await session.commit()
        await session.close()

        # A fresh DB session sees the accepted contract and its payout ledger,
        # proving that lifecycle state is persisted rather than held in memory.
        restarted_session = async_sessionmaker(engine, expire_on_commit=False)()
        persisted = await restarted_session.scalar(
            select(NatSupplyDeal).where(NatSupplyDeal.id == deal_id)
        )
        payout_rows = (await restarted_session.execute(
            select(NatSupplyDealSettlement).where(
                NatSupplyDealSettlement.deal_id == deal_id,
                NatSupplyDealSettlement.settlement_type == "FIXED_CASH",
            )
        )).scalars().all()
        assert persisted is not None and persisted.status == "ACTIVE"
        assert persisted.fixed_cash_paid == 100
        assert len(payout_rows) == 1 and payout_rows[0].cash_amount == 100
        await restarted_session.close()
    finally:
        await session.close()
        await engine.dispose()


async def _concurrent_accept_cannot_double_pay() -> None:
    # A file-backed database gives the contenders independent DB connections,
    # unlike SQLite's single-connection in-memory test fixture.
    with TemporaryDirectory(prefix="nat-deal-concurrency-") as temp_dir:
        database_url = f"sqlite+aiosqlite:///{Path(temp_dir) / 'deals.sqlite3'}"
        engine, session, buyer, supplier = await _fixture(database_url)
        now = get_game_now().replace(microsecond=0)
        offer = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=10, discount_pct=0, term_seconds=1800,
            reward_type="FIXED_CASH", fixed_cash=100, now=now,
        )
        await session.commit()
        deal_id, supplier_id = offer.id, supplier.id
        await session.close()
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def concurrent_accept():
            async with sessions() as contender:
                try:
                    async with contender.begin():
                        actor = await contender.get(NatCompany, supplier_id)
                        return await SupplyDealService.accept(
                            contender, actor, deal_id, now=now,
                        )
                except Exception as exc:
                    return exc

        outcomes = await asyncio.gather(concurrent_accept(), concurrent_accept())
        assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1, outcomes
        async with sessions() as verify:
            rows = (await verify.execute(select(NatSupplyDealSettlement).where(
                NatSupplyDealSettlement.deal_id == deal_id,
                NatSupplyDealSettlement.settlement_type == "FIXED_CASH",
            ))).scalars().all()
            buyer_after = await verify.get(NatCompany, buyer.id)
            supplier_after = await verify.get(NatCompany, supplier_id)
            assert len(rows) == 1
            assert buyer_after.cash == 99_900
            assert supplier_after.cash == 10_100
        await engine.dispose()


async def _offline_interval_intersects_only_active_deal_time() -> None:
    engine, session, buyer, supplier = await _fixture()
    now = get_game_now().replace(microsecond=0)
    offline_start = now - timedelta(hours=3)
    supplier_business = await session.scalar(
        select(NatBusiness).where(NatBusiness.company_id == supplier.id)
    )
    supplier_business.business_type = "artesian_well"
    supplier_business.specialization = "water"
    supplier.specialization = "water"
    supplier_business.last_settled_at = offline_start
    supplier_business.base_maintenance_per_hour = 0
    buyer_businesses = [NatBusiness(
        company_id=buyer.id, business_type="diesel_power_station", specialization="power_engineer",
        stage=1, status="ACTIVE", last_settled_at=offline_start,
    )]
    session.add_all(buyer_businesses)
    session.add_all([
        NatInventory(company_id=buyer.id, item_id="fuel_diesel", quantity=100, avg_cost_basis=1),
        NatInventory(company_id=supplier.id, item_id="energy", quantity=100, avg_cost_basis=10),
    ])
    await session.flush()
    try:
        accepted_at = now - timedelta(hours=2)
        offer = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="water",
            quantity_per_hour=100, discount_pct=20, term_seconds=3600,
            reward_type="PROFIT_SHARE", profit_share_pct=10, now=accepted_at,
        )
        await SupplyDealService.accept(session, supplier, offer.id, now=accepted_at)
        # A supplier refresh cannot close a past contract before the buyer
        # lazily settles the exact historical interval.
        await IdleEconomyService.settle_company(session, supplier.id, now=now, _process_deals=False)
        assert offer.status == "ACTIVE"
        assert offer.settlement_cursor < offer.expires_at
        settlement = await IdleEconomyService.settle_company(session, buyer.id, now=now)
        await session.flush()
        buyer_water = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == buyer.id, NatInventory.item_id == "water"
        ))
        buyer_energy = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == buyer.id, NatInventory.item_id == "energy"
        ))
        deal_rows = (await session.execute(select(NatSupplyDeal))).scalars().all()
        entries = (await session.execute(select(NatSupplyDealSettlement).where(
            NatSupplyDealSettlement.deal_id == offer.id
        ))).scalars().all()
        delivery = [row for row in entries if row.settlement_type == "DELIVERY"]
        share = [row for row in entries if row.settlement_type == "PROFIT_SHARE"]
        assert deal_rows[0].status == "COMPLETED"
        assert len(delivery) == 1, entries
        assert abs(delivery[0].quantity - (100 / 6)) < 1e-4, delivery[0].quantity
        assert buyer_water is None or buyer_water.quantity < 1e-6
        assert buyer_energy is not None and buyer_energy.quantity > 0, buyer_energy.quantity if buyer_energy else None
        assert share == []
        assert settlement["profit_share_paid_cash"] == 0
        assert buyer.cash >= 0
        await session.commit()
    finally:
        await session.close()
        await engine.dispose()


async def _profit_share_is_positive_only_and_idempotent() -> None:
    engine, session, buyer, supplier = await _fixture()
    now = get_game_now().replace(microsecond=0)
    start = now - timedelta(hours=1)
    earning_business = NatBusiness(
        company_id=buyer.id, business_type="retail_chain", specialization="retail",
        stage=1, status="ACTIVE", last_settled_at=start,
    )
    session.add(earning_business)
    await session.flush()
    try:
        offer = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=10, discount_pct=0, term_seconds=7200,
            reward_type="PROFIT_SHARE", profit_share_pct=10, now=start,
        )
        await SupplyDealService.accept(session, supplier, offer.id, now=start)
        slice_ = [{
            "business_id": earning_business.id, "start": start,
            "end": now, "net_profit": 1_000.0,
        }]
        paid = await SupplyDealService.settle_profit_share(
            session, buyer, slice_, cash_available=30, now=now
        )
        assert paid == 30
        assert supplier.cash == 10_030
        assert await SupplyDealService.settle_profit_share(
            session, buyer, slice_, cash_available=30, now=now
        ) == 0
        assert await SupplyDealService.settle_profit_share(
            session, buyer, [{**slice_[0], "start": now, "end": now + timedelta(minutes=1), "net_profit": -100}],
            cash_available=1000, now=now,
        ) == 0
        row = await session.scalar(select(NatSupplyDeal).where(NatSupplyDeal.id == offer.id))
        assert row.profit_share_paid == 30
        await session.commit()
    finally:
        await session.close()
        await engine.dispose()


async def _delivery_respects_supplier_inventory_demand_quota_and_cash() -> None:
    engine, session, buyer, supplier = await _fixture()
    now = get_game_now().replace(microsecond=0)
    start = now - timedelta(minutes=15)
    buyer_business = NatBusiness(
        company_id=buyer.id, business_type="coal_open_pit", specialization="miner",
        stage=1, status="ACTIVE", last_settled_at=start,
    )
    supplier_stock = NatInventory(
        company_id=supplier.id, item_id="energy", quantity=7, avg_cost_basis=1,
    )
    buyer_inputs = [
        NatInventory(company_id=buyer.id, item_id=item, quantity=100, avg_cost_basis=1)
        for item in ("water", "fuel_diesel", "food")
    ]
    session.add_all([buyer_business, supplier_stock, *buyer_inputs])
    await session.flush()
    try:
        offer = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=100, discount_pct=20, term_seconds=1800,
            reward_type="PROFIT_SHARE", profit_share_pct=1, now=start,
        )
        await SupplyDealService.accept(session, supplier, offer.id, now=start)
        spec = get_business_spec("coal_open_pit")
        reference = await SupplyDealService.current_reference_price(
            session, "energy", exclude_company_id=buyer.id,
        )
        price = reference * 0.8
        before_buyer_cash, before_supplier_cash = buyer.cash, supplier.cash
        transfers = await SupplyDealService.fulfill_resource_interval(
            session, buyer, buyer_business, spec,
            start=start, end=start + timedelta(minutes=15), now=now,
        )
        assert len(transfers) == 1
        assert transfers[0]["quantity"] == 7  # below the 25-unit quota and 22-unit demand
        buyer_energy = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == buyer.id, NatInventory.item_id == "energy"
        ))
        assert buyer_energy is not None and buyer_energy.quantity == 7
        assert supplier_stock.quantity == 0
        assert abs((before_buyer_cash - buyer.cash) - 7 * price) < 1e-5
        assert abs((supplier.cash - before_supplier_cash) - 7 * price) < 1e-5

        buyer.cash = 0
        supplier_stock.quantity = 10
        no_cash = await SupplyDealService.fulfill_resource_interval(
            session, buyer, buyer_business, spec,
            start=start + timedelta(minutes=15), end=start + timedelta(minutes=30), now=now,
        )
        assert no_cash == []
        assert buyer.cash == 0
        assert supplier_stock.quantity == 10
        await session.commit()
    finally:
        await session.close()
        await engine.dispose()


async def _api_rejects_non_participants() -> None:
    engine, session, buyer, supplier = await _fixture()
    outsider_user = User(tg_id=991303, full_name="Outsider")
    session.add(outsider_user)
    await session.flush()
    outsider = NatCompany(user_id=outsider_user.id, name="Outsider Co", specialization="miner")
    session.add(outsider)
    await session.flush()
    current = {"company": buyer}
    app = FastAPI()
    app.include_router(supply_deal_router)

    async def override_company():
        return current["company"]

    async def override_session():
        yield session

    app.dependency_overrides[get_current_company] = override_company
    app.dependency_overrides[get_db_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post("/market/deals", headers={"Idempotency-Key": "deal-api-create"}, json={
                "supplier_company_id": supplier.id, "item_id": "energy", "quantity_per_hour": 5,
                "discount_pct": 10, "term_seconds": 600, "reward_type": "PROFIT_SHARE",
                "profit_share_pct": 5,
            })
            assert created.status_code == 200, created.text
            deal_id = created.json()["id"]
            current["company"] = outsider
            hidden = await client.get(f"/market/deals/{deal_id}")
            assert hidden.status_code == 404
            denied = await client.post(
                f"/market/deals/{deal_id}/accept",
                headers={"Idempotency-Key": "deal-api-outsider-accept"},
            )
            assert denied.status_code == 400
            current["company"] = supplier
            accepted = await client.post(
                f"/market/deals/{deal_id}/accept",
                headers={"Idempotency-Key": "deal-api-accept"},
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["status"] == "ACTIVE"
            deal = await session.scalar(select(NatSupplyDeal).where(NatSupplyDeal.id == deal_id))
            now = get_game_now().replace(tzinfo=None)
            deal.starts_at = now - timedelta(minutes=20)
            deal.expires_at = now - timedelta(minutes=10)
            deal.settlement_cursor = deal.starts_at
            current["company"] = supplier
            active = await client.get("/market/deals/active")
            assert active.status_code == 200, active.text
            assert all(row["id"] != deal_id for row in active.json()["items"])
            historic = await client.get("/market/deals/history")
            assert historic.status_code == 200, historic.text
            assert next(row for row in historic.json()["items"] if row["id"] == deal_id)["status"] == "COMPLETED"
        await session.commit()
    finally:
        app.dependency_overrides.clear()
        await session.close()
        await engine.dispose()


async def _bankruptcy_breaches_and_reset_removes_deals() -> None:
    engine, session, buyer, supplier = await _fixture()
    now = get_game_now().replace(microsecond=0)
    try:
        offer = await SupplyDealService.create_offer(
            session, buyer, supplier_company_id=supplier.id, item_id="energy",
            quantity_per_hour=10, discount_pct=0, term_seconds=1800,
            reward_type="FIXED_CASH", fixed_cash=100, now=now,
        )
        await SupplyDealService.accept(session, supplier, offer.id, now=now)
        settled_before = (await session.execute(select(NatSupplyDealSettlement).where(
            NatSupplyDealSettlement.deal_id == offer.id
        ))).scalars().all()
        assert len(settled_before) == 1
        await SupplyDealService.bankruptcy_terminate(session, buyer.id, now=now + timedelta(minutes=5))
        assert offer.status == "BREACHED"
        still_auditable = await session.scalar(select(NatSupplyDealSettlement.id).where(
            NatSupplyDealSettlement.deal_id == offer.id
        ))
        assert still_auditable is not None

        await CompanyService.reset_company_for_user(session, buyer.user_id, commit=False)
        assert await session.scalar(select(NatSupplyDeal.id).where(
            NatSupplyDeal.id == offer.id
        )) is None
        assert await session.scalar(select(NatSupplyDealSettlement.id).where(
            NatSupplyDealSettlement.deal_id == offer.id
        )) is None
        await session.commit()
    finally:
        await session.close()
        await engine.dispose()


async def run_async() -> None:
    await _lifecycle_and_limits()
    await _fixed_payout_is_atomic()
    await _concurrent_accept_cannot_double_pay()
    await _delivery_respects_supplier_inventory_demand_quota_and_cash()
    await _offline_interval_intersects_only_active_deal_time()
    await _profit_share_is_positive_only_and_idempotent()
    await _api_rejects_non_participants()
    await _bankruptcy_breaches_and_reset_removes_deals()
    print("NATBIRZHA player supply deal lifecycle: PASS")


def test_player_supply_deals() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    asyncio.run(run_async())
