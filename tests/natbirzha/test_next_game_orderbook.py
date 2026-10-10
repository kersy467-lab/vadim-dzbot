import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameInventory, NatNextGameMarketOrder,
    NatNextGameMarketTrade,
)
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import NextGameService


def test_limit_order_match_uses_older_seller_price_and_refunds_buy_escrow():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81001, "Поставщик")
            await NextGameService.create_company(session, 81002, "Покупатель")
            await NextGameService.trade(session, 81001, "energy", "BUY", 5)

            ask = await NextGameMarketService.create_limit_order(
                session, 81001, "energy", "SELL", 5, 5,
                now=datetime(2026, 10, 10, 12, 0),
            )
            bid = await NextGameMarketService.create_limit_order(
                session, 81002, "energy", "BUY", 3, 8,
                now=datetime(2026, 10, 10, 12, 1),
            )

            assert bid["executed_quantity"] == 3
            assert bid["remaining_quantity"] == 0
            assert bid["trades"][0]["price"] == 5
            assert bid["trades"][0]["quantity"] == 3
            stored_ask = await session.get(NatNextGameMarketOrder, ask["order"]["id"])
            assert stored_ask.remaining_quantity == 2
            buyer = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 81002
            ))
            seller = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 81001
            ))
            item = await session.scalar(select(NatNextGameInventory).where(
                NatNextGameInventory.company_id == buyer.id,
                NatNextGameInventory.item_id == "energy",
            ))
            trade = await session.scalar(select(NatNextGameMarketTrade))
            assert buyer.cash == pytest.approx(9_985)
            assert seller.cash == pytest.approx(9_955)
            assert item.quantity == 3
            assert trade.buyer_company_id == buyer.id
            assert trade.seller_company_id == seller.id
            assert trade.price == 5
        await engine.dispose()

    asyncio.run(check())


def test_limit_order_match_uses_older_buyer_price_and_keeps_partial_escrow():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81101, "Покупатель")
            await NextGameService.create_company(session, 81102, "Поставщик")
            await NextGameService.trade(session, 81102, "energy", "BUY", 2)
            bid = await NextGameMarketService.create_limit_order(
                session, 81101, "energy", "BUY", 4, 10,
                now=datetime(2026, 10, 10, 12, 0),
            )
            ask = await NextGameMarketService.create_limit_order(
                session, 81102, "energy", "SELL", 2, 8,
                now=datetime(2026, 10, 10, 12, 1),
            )
            buyer = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 81101
            ))
            stored_bid = await session.get(NatNextGameMarketOrder, bid["order"]["id"])
            assert ask["trades"][0]["price"] == 10
            assert ask["executed_quantity"] == 2
            assert stored_bid.remaining_quantity == 2
            assert stored_bid.reserved_cash == pytest.approx(20)
            assert buyer.cash == pytest.approx(9_960)
        await engine.dispose()

    asyncio.run(check())


def test_cancel_releases_open_buy_cash_and_sell_inventory_reservations():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81201, "Компания")
            await NextGameService.trade(session, 81201, "energy", "BUY", 5)
            company = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 81201
            ))
            stock = await session.scalar(select(NatNextGameInventory).where(
                NatNextGameInventory.company_id == company.id,
                NatNextGameInventory.item_id == "energy",
            ))
            before_buy = company.cash
            buy = await NextGameMarketService.create_limit_order(
                session, 81201, "energy", "BUY", 4, 10,
            )
            assert company.cash == pytest.approx(before_buy - 40)
            await NextGameMarketService.cancel_order(session, 81201, buy["order"]["id"])
            assert company.cash == pytest.approx(before_buy)

            sell = await NextGameMarketService.create_limit_order(
                session, 81201, "energy", "SELL", 3, 10,
            )
            assert stock.quantity == pytest.approx(2)
            await NextGameMarketService.cancel_order(session, 81201, sell["order"]["id"])
            assert stock.quantity == pytest.approx(5)
        await engine.dispose()

    asyncio.run(check())


def test_small_positive_limit_order_below_one_cent_is_allowed():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81299, "Малый ордер")
            order = await NextGameMarketService.create_limit_order(
                session, 81299, "energy", "BUY", 1, 0.005,
            )
            assert order["order"]["limit_price"] == pytest.approx(0.005)
            assert order["order"]["reserved_cash"] == pytest.approx(0.005)
        await engine.dispose()

    asyncio.run(check())


def test_self_orders_are_skipped_without_blocking_a_different_company():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81301, "Сам себе")
            await NextGameService.create_company(session, 81302, "Поставщик")
            await NextGameService.trade(session, 81301, "energy", "BUY", 1)
            await NextGameService.trade(session, 81302, "energy", "BUY", 1)
            own_ask = await NextGameMarketService.create_limit_order(
                session, 81301, "energy", "SELL", 1, 4,
            )
            other_ask = await NextGameMarketService.create_limit_order(
                session, 81302, "energy", "SELL", 1, 6,
            )
            own_bid = await NextGameMarketService.create_limit_order(
                session, 81301, "energy", "BUY", 1, 10,
            )
            stored_own_ask = await session.get(NatNextGameMarketOrder, own_ask["order"]["id"])
            stored_other_ask = await session.get(NatNextGameMarketOrder, other_ask["order"]["id"])
            assert own_bid["executed_quantity"] == 1
            assert own_bid["trades"][0]["seller_company_id"] != own_bid["trades"][0]["buyer_company_id"]
            assert own_bid["trades"][0]["seller_company_id"] == (
                await session.scalar(select(NatNextGameCompany.id).where(
                    NatNextGameCompany.owner_tg_id == 81302
                ))
            )
            assert stored_own_ask.remaining_quantity == 1
            assert stored_other_ask.remaining_quantity == 0
        await engine.dispose()

    asyncio.run(check())


def test_npc_trades_and_production_cannot_consume_reserved_stock_or_cash():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81401, "Резервы")
            await NextGameService.trade(session, 81401, "energy", "BUY", 3)
            await NextGameService.select_sector(session, 81401, "resources")
            await NextGameService.select_branch(session, 81401, "ore_mining")
            await NextGameService.build_facility(
                session, 81401, now=datetime(2026, 10, 10, 12, 0)
            )
            company = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 81401
            ))
            await NextGameMarketService.create_limit_order(
                session, 81401, "energy", "SELL", 3, 10,
            )
            with pytest.raises(ValueError, match="Недостаточно товара"):
                await NextGameService.trade(session, 81401, "energy", "SELL", 1)
            with pytest.raises(ValueError, match="Недостаточно товара"):
                await NextGameMarketService.create_limit_order(
                    session, 81401, "energy", "SELL", 1, 9,
                )

            company.cash = 10_000
            await NextGameMarketService.create_limit_order(
                session, 81401, "water", "BUY", 9_900, 1,
            )
            before_cash = company.cash
            with pytest.raises(ValueError, match="Недостаточно cash"):
                await NextGameService.trade(session, 81401, "energy", "BUY", 100)
            with pytest.raises(ValueError, match="Недостаточно cash"):
                await NextGameMarketService.create_limit_order(
                    session, 81401, "energy", "BUY", 1, 200,
                )
            assert company.cash == pytest.approx(before_cash)

            # Reserved energy is absent from available production inputs.
            blocked = await NextGameService.settle_company(
                session, 81401, now=datetime(2026, 10, 10, 12, 10)
            )
            assert blocked["cycles_completed"] == 0
            assert blocked["blocked"]
        await engine.dispose()

    asyncio.run(check())


@pytest.mark.parametrize("item_id,side,quantity,price", [
    ("not-real", "BUY", 1, 1),
    ("energy", "HOLD", 1, 1),
    ("energy", "BUY", 0, 1),
    ("energy", "BUY", float("nan"), 1),
    ("energy", "BUY", 0.00001, 1),
    ("energy", "BUY", 10_000.0001, 1),
    ("energy", "BUY", 1, 0),
    ("energy", "BUY", 1, 1.00009),
    ("energy", "BUY", 1, float("inf")),
])
def test_invalid_limit_order_values_are_rejected(item_id, side, quantity, price):
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81501, "Валидация")
            with pytest.raises(ValueError):
                await NextGameMarketService.create_limit_order(
                    session, 81501, item_id, side, quantity, price,
                )
            assert await session.scalar(select(NatNextGameMarketOrder.id)) is None
        await engine.dispose()

    asyncio.run(check())


def test_order_funding_failure_leaves_no_order_or_balance_change():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81601, "Без денег")
            await session.commit()
            company = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 81601
            ))
            company.cash = 5
            await session.commit()
            with pytest.raises(ValueError, match="Недостаточно cash"):
                await NextGameMarketService.create_limit_order(
                    session, 81601, "energy", "BUY", 1, 10,
                )
            await session.rollback()
            async with sessions() as verify:
                persisted = await verify.scalar(select(NatNextGameCompany).where(
                    NatNextGameCompany.owner_tg_id == 81601
                ))
                assert persisted.cash == 5
                assert await verify.scalar(select(NatNextGameMarketOrder.id)) is None
        await engine.dispose()

    asyncio.run(check())


def test_market_snapshot_has_open_book_own_orders_and_execution_history():
    async def check():
        engine, sessions = await _database_async()
        async with sessions() as session:
            await NextGameService.create_company(session, 81701, "Первая")
            await NextGameService.create_company(session, 81702, "Вторая")
            await NextGameService.select_sector(session, 81701, "resources")
            await NextGameService.select_branch(session, 81701, "ore_mining")
            await NextGameService.trade(session, 81702, "energy", "BUY", 2)
            bid = await NextGameMarketService.create_limit_order(
                session, 81701, "energy", "BUY", 2, 5,
            )
            await NextGameMarketService.create_limit_order(
                session, 81702, "energy", "SELL", 1, 4,
            )
            book = await NextGameMarketService.market_snapshot(
                session, company_id=bid["order"]["company_id"], item_ids={"energy"},
            )
            assert book["open_orders"]
            assert book["my_orders"][0]["side"] == "BUY"
            assert book["trades"][0]["buyer_name"] == "Первая"
            assert book["trades"][0]["seller_name"] == "Вторая"
            assert book["trades"][0]["item_id"] == "energy"
            assert book["trades"][0]["quantity"] == 1
            snapshot = await NextGameService.snapshot(session, 81701)
            assert snapshot["market_orders"]["open_orders"]
            assert snapshot["market_orders"]["my_orders"]
            assert snapshot["market_orders"]["trades"][0]["buyer_name"] == "Первая"
        await engine.dispose()

    asyncio.run(check())


def test_market_models_are_exported_from_the_model_registry():
    from backend.natbirzha import models

    assert models.NatNextGameMarketOrder is NatNextGameMarketOrder
    assert models.NatNextGameMarketTrade is NatNextGameMarketTrade


def test_concurrent_market_posts_cannot_overfill_a_single_maker_order():
    async def check():
        database = Path(__file__).with_name(f".orderbook-{uuid4().hex}.sqlite")
        engine = create_async_engine(f"sqlite+aiosqlite:///{database}", connect_args={"timeout": 10})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            await NextGameService.create_company(session, 81901, "Поставщик")
            await NextGameService.create_company(session, 81902, "Покупатель 1")
            await NextGameService.create_company(session, 81903, "Покупатель 2")
            await NextGameService.trade(session, 81901, "energy", "BUY", 1)
            ask = await NextGameMarketService.create_limit_order(
                session, 81901, "energy", "SELL", 1, 4,
            )
            await session.commit()

        async def submit(owner_id):
            async with sessions() as session:
                result = await NextGameMarketService.create_limit_order(
                    session, owner_id, "energy", "BUY", 1, 5,
                )
                await session.commit()
                return result

        first, second = await asyncio.gather(submit(81902), submit(81903))
        assert first["executed_quantity"] + second["executed_quantity"] == pytest.approx(1)
        async with sessions() as session:
            trade_count = await session.scalar(select(func.count()).select_from(NatNextGameMarketTrade))
            stored_ask = await session.get(NatNextGameMarketOrder, ask["order"]["id"])
            assert trade_count == 1
            assert stored_ask.status == "FILLED"
            assert stored_ask.remaining_quantity == 0
        await engine.dispose()
        database.unlink(missing_ok=True)

    asyncio.run(check())


def test_postgresql_orderbook_locks_companies_in_stable_id_order():
    class ScalarResult:
        def all(self):
            return []

    class FakeSession:
        def __init__(self):
            self.statements = []

        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        async def scalars(self, statement):
            self.statements.append(statement)
            return ScalarResult()

        async def scalar(self, statement):
            self.statements.append(statement)
            return object()

    async def check():
        session = FakeSession()
        await NextGameMarketService.lock_orderbook(session)
        company_lock_sql = next(
            str(statement.compile(dialect=postgresql.dialect()))
            for statement in session.statements
            if "nat_next_game_companies" in str(statement)
        )
        assert "ORDER BY nat_next_game_companies.id" in company_lock_sql
        assert "FOR UPDATE" in company_lock_sql

    asyncio.run(check())


async def _database_async():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions
