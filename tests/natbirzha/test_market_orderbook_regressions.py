"""Regression checks for order visibility and crossed commodity order matching."""

import asyncio
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401 - register all NATBIRZHA tables
from backend.natbirzha.api.market_routes import CancelOrderRequest, cancel_order_body, get_orderbook
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketTrade
from backend.natbirzha.models.stocks import NatHourlyDividendAccrual, NatStock
from backend.natbirzha.config import get_game_now
from backend.natbirzha.services.market_service import MarketService


def test_market_orderbook_returns_active_orders_for_authenticated_company() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            owner = NatCompany(user_id=70_001, name="Order owner", specialization="miner", cash=1_000)
            other = NatCompany(user_id=70_002, name="Other trader", specialization="agrarian", cash=1_000)
            session.add_all([owner, other])
            await session.flush()
            inventory = NatInventory(
                company_id=owner.id,
                item_id="steel",
                quantity=3.0,
                reserved_quantity=0.0,
                avg_cost_basis=10.0,
            )
            session.add(inventory)
            await session.flush()
            own_order = await MarketService.create_order(
                session, owner, "BUY", "steel", 90.0, 2.0, commit=False
            )
            await MarketService.create_order(session, other, "BUY", "steel", 80.0, 1.0, commit=False)
            own_sell = await MarketService.create_order(
                session, owner, "SELL", "steel", 100.0, 2.0, commit=False
            )

            book = await get_orderbook(item_id="steel", company=owner, session=session)

            assert book["user_orders"] == [
                {
                    "id": own_order.id,
                    "order_type": "BUY",
                    "price": 90.0,
                    "remaining_quantity": 2.0,
                },
                {
                    "id": own_sell.id,
                    "order_type": "SELL",
                    "price": 100.0,
                    "remaining_quantity": 2.0,
                },
            ]

            cancelled = await cancel_order_body(
                req=CancelOrderRequest(order_id=own_order.id),
                idempotency_key=None,
                company=owner,
                session=session,
            )
            assert cancelled == {"success": True, "cancelled_order_id": own_order.id}
            assert owner.cash == 1_000.0
            cancelled_sell = await cancel_order_body(
                req=CancelOrderRequest(order_id=own_sell.id),
                idempotency_key=None,
                company=owner,
                session=session,
            )
            assert cancelled_sell == {"success": True, "cancelled_order_id": own_sell.id}
            assert inventory.quantity == 3.0
            assert inventory.reserved_quantity == 0.0
        await engine.dispose()

    asyncio.run(check())


def test_matching_skips_top_bid_when_only_its_own_ask_is_available() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            owner = NatCompany(user_id=70_011, name="Crossed trader", specialization="miner", cash=1_000)
            buyer = NatCompany(user_id=70_012, name="Second buyer", specialization="agrarian", cash=1_000)
            session.add_all([owner, buyer])
            await session.flush()
            session.add(NatInventory(
                company_id=owner.id,
                item_id="steel",
                quantity=1.0,
                reserved_quantity=0.0,
                avg_cost_basis=4.0,
            ))
            await session.flush()

            await MarketService.create_order(session, owner, "BUY", "steel", 15.0, 1.0, commit=False)
            await MarketService.create_order(session, owner, "SELL", "steel", 5.0, 1.0, commit=False)
            buyer_order = await MarketService.create_order(
                session, buyer, "BUY", "steel", 10.0, 1.0, commit=False
            )

            assert buyer_order.status == "FILLED"
            trade = await session.scalar(select(NatMarketTrade).where(
                NatMarketTrade.buyer_company_id == buyer.id,
                NatMarketTrade.seller_company_id == owner.id,
            ))
            assert trade is not None and trade.price == 5.0 and trade.quantity == 1.0
        await engine.dispose()

    asyncio.run(check())


def test_ipo_company_withholds_dividends_from_net_market_sale_proceeds() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now()
        async with sessions() as session:
            seller = NatCompany(user_id=70_021, name="IPO Seller", specialization="miner", cash=100)
            buyer = NatCompany(user_id=70_022, name="Market Buyer", specialization="agrarian", cash=100)
            session.add_all([seller, buyer])
            await session.flush()
            stock = NatStock(
                company_id=seller.id, total_shares=100, founder_shares=100,
                float_shares=0, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True,
                ipo_date=now - timedelta(hours=1),
                dividend_eligible_from=now - timedelta(hours=1),
                created_at=now - timedelta(hours=1),
            )
            seller_inventory = NatInventory(
                company_id=seller.id, item_id="steel", quantity=1,
                reserved_quantity=0, avg_cost_basis=5,
            )
            session.add_all([stock, seller_inventory])
            await session.flush()

            await MarketService.create_order(
                session, seller, "SELL", "steel", 10, 1, commit=False
            )
            await MarketService.create_order(
                session, buyer, "BUY", "steel", 10, 1, commit=False
            )
            accrual = await session.scalar(select(NatHourlyDividendAccrual).where(
                NatHourlyDividendAccrual.stock_id == stock.id
            ))

            # A 1% exchange fee is charged first; the configured 10% share is
            # withheld from the 9.90 actually credited to the seller.
            assert accrual is not None
            assert accrual.closed_profit == 9.9
            assert accrual.dividend_pool == 0.99
            assert seller.cash == 108.91

        await engine.dispose()

    asyncio.run(check())


if __name__ == "__main__":
    test_market_orderbook_returns_active_orders_for_authenticated_company()
    test_matching_skips_top_bid_when_only_its_own_ask_is_available()
    test_ipo_company_withholds_dividends_from_net_market_sale_proceeds()
    print("NATBIRZHA market orderbook regressions: PASS")
