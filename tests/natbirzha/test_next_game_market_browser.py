"""Commodity browser integration with actual isolated order executions."""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameMarketTrade
from backend.natbirzha.next_game_catalog import get_next_game_items
from backend.natbirzha.services.next_game_market_browser_service import NextGameMarketBrowserService
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import NextGameService


def test_browser_contains_all_goods_actual_book_history_and_own_closed_orders():
    async def check():
        engine, sessions = await database()
        async with sessions() as session:
            await NextGameService.create_company(session, 94001, "Поставщик")
            await NextGameService.create_company(session, 94002, "Покупатель")
            await NextGameService.select_sector(session, 94001, "resources")
            await NextGameService.select_branch(session, 94001, "ore_mining")
            await NextGameService.build_facility(session, 94001)
            catalog = await NextGameMarketBrowserService.catalog(session, 94001)
            assert {row["id"] for row in catalog["items"]} == set(get_next_game_items())
            assert any(row["isIndustry"] for row in catalog["items"])
            await NextGameService.trade(session, 94001, "energy", "BUY", 8)
            ask = await NextGameMarketService.create_limit_order(session, 94001, "energy", "SELL", 5, 10)
            await NextGameMarketService.create_limit_order(session, 94002, "energy", "BUY", 3, 11)
            bid = await NextGameMarketService.create_limit_order(session, 94002, "energy", "BUY", 1, 7)
            await NextGameMarketService.cancel_order(session, 94002, bid["order"]["id"])
            detail = await NextGameMarketBrowserService.item(session, 94002, "energy")
            assert detail["asks"][0]["id"] == ask["order"]["id"]
            assert detail["asks"][0]["remaining_quantity"] == 2
            assert detail["bids"] == []
            assert detail["history"][0]["price"] == 10
            assert detail["history"][0]["quantity"] == 3
            assert detail["reference_price"] == 10
            assert detail["inventory_quantity"] == 3
            assert {row["status"] for row in detail["user_orders"]} == {"FILLED", "CANCELLED"}
            assert detail["npc"]["buy_price"] > detail["npc"]["sell_price"]
            empty_item = next(item for item in get_next_game_items() if item != "energy")
            empty = await NextGameMarketBrowserService.item(session, 94002, empty_item)
            assert empty["history"] == [] and empty["reference_price"] is None
        await engine.dispose()
    asyncio.run(check())


def test_liquidity_aggregates_all_real_executions_without_history_limit():
    async def check():
        engine, sessions = await database()
        now = datetime(2026, 10, 10, 12)
        async with sessions() as session:
            seller = await NextGameService.create_company(session, 94101, "Продавец")
            buyer = await NextGameService.create_company(session, 94102, "Покупатель")
            seller_id, buyer_id = seller["company"]["id"], buyer["company"]["id"]
            for index in range(250):
                session.add(NatNextGameMarketTrade(
                    buy_order_id=index + 1, sell_order_id=index + 1000,
                    buyer_company_id=buyer_id, seller_company_id=seller_id,
                    item_id="energy", quantity=2, price=3,
                    executed_at=now - timedelta(minutes=index),
                ))
            session.add(NatNextGameMarketTrade(
                buy_order_id=900, sell_order_id=901, buyer_company_id=buyer_id,
                seller_company_id=seller_id, item_id="energy", quantity=100,
                price=100, executed_at=now - timedelta(hours=25),
            ))
            await session.flush()
            result = await NextGameMarketBrowserService.liquidity(session, now=now)
            assert result["items"][0]["sale_count"] == 250
            assert result["items"][0]["quantity"] == 500
            assert result["items"][0]["buyer_cash_paid"] == 1500
        await engine.dispose()
    asyncio.run(check())


async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions
