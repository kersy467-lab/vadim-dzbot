"""State cash advances secured by sell orders must remain auditable and safe."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401 - register all NATBIRZHA tables
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.market_advance_service import MarketAdvanceService
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.migrations import _migrate_v21_state_market_advances
from sqlalchemy import text


async def _fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions


async def _company(session, user_id: int, name: str, cash: float = 0.0) -> NatCompany:
    company = NatCompany(user_id=user_id, name=name, specialization="miner", cash=cash)
    session.add(company)
    await session.flush()
    return company


async def _seed_external_trades(session, *, prices=(100.0, 100.0, 100.0)) -> None:
    now = get_game_now()
    for index, price in enumerate(prices):
        buyer = await _company(session, 880_000 + index * 2, f"Buyer {index}")
        seller = await _company(session, 880_001 + index * 2, f"Seller {index}")
        session.add(NatMarketTrade(
            buyer_company_id=buyer.id,
            seller_company_id=seller.id,
            item_id="steel",
            price=price,
            quantity=10.0,
            total_amount=price * 10,
            fee_amount=0,
            executed_at=now - timedelta(minutes=30 - index),
        ))
    await session.flush()


def test_state_advance_is_capped_and_market_sale_returns_funded_proceeds_to_treasury() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            await _seed_external_trades(session)
            treasury = NatStateTreasury(id=1, cash=100_000)
            seller = await _company(session, 880_100, "Financed seller")
            buyer = await _company(session, 880_101, "Market buyer", cash=100_000)
            session.add(treasury)
            inventory = NatInventory(
                company_id=seller.id, item_id="steel", quantity=1_000,
                reserved_quantity=0, avg_cost_basis=10,
            )
            session.add(inventory)
            await session.flush()

            ask = await MarketService.create_order(
                session, seller, "SELL", "steel", 100, 500, commit=False
            )
            assert ask.state_advance_amount == 30_000
            assert ask.state_advance_quantity == 300
            assert ask.state_advance_remaining_quantity == 300
            assert ask.state_advance_reference_price == 100
            assert seller.cash == 30_000
            assert treasury.cash == 70_000
            assert inventory.reserved_quantity == 500

            await MarketService.create_order(
                session, buyer, "BUY", "steel", 100, 300, commit=False
            )
            trade = await session.scalar(select(NatMarketTrade).where(
                NatMarketTrade.sell_order_id == ask.id
            ))
            assert trade is not None
            assert trade.state_repayment_amount == 30_000
            assert treasury.cash == 100_000
            assert seller.cash == 30_000, "funded quantity must not pay seller twice"
            assert ask.remaining_qty == 200
            assert ask.state_advance_remaining_quantity == 0

            assert await MarketService.cancel_order(session, seller, ask.id, commit=False)
            assert inventory.reserved_quantity == 0
        await engine.dispose()

    asyncio.run(check())


def test_funded_and_unfunded_parts_settle_to_their_respective_recipients() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            await _seed_external_trades(session)
            treasury = NatStateTreasury(id=1, cash=100_000)
            seller = await _company(session, 880_110, "Mixed seller")
            buyer = await _company(session, 880_111, "Mixed buyer", cash=100_000)
            session.add_all([treasury, NatInventory(
                company_id=seller.id, item_id="steel", quantity=500,
                reserved_quantity=0, avg_cost_basis=10,
            )])
            await session.flush()

            ask = await MarketService.create_order(
                session, seller, "SELL", "steel", 100, 400, commit=False
            )
            await MarketService.create_order(
                session, buyer, "BUY", "steel", 100, 400, commit=False
            )

            trade = await session.scalar(select(NatMarketTrade).where(
                NatMarketTrade.sell_order_id == ask.id
            ))
            assert trade is not None
            assert trade.state_repayment_amount == 30_000
            assert treasury.cash == 100_000
            assert trade.fee_amount == 100
            assert seller.cash == pytest.approx(39_900)
            assert ask.status == "FILLED"
        await engine.dispose()

    asyncio.run(check())


def test_one_collusive_high_price_trade_does_not_raise_advance_reference() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            await _seed_external_trades(session)
            pump_buyer = await _company(session, 880_120, "Pump buyer")
            pump_seller = await _company(session, 880_121, "Pump seller")
            now = get_game_now()
            session.add(NatMarketTrade(
                buyer_company_id=pump_buyer.id,
                seller_company_id=pump_seller.id,
                item_id="steel",
                price=500,
                quantity=1,
                total_amount=500,
                fee_amount=0,
                executed_at=now,
            ))
            treasury = NatStateTreasury(id=1, cash=100_000)
            seller = await _company(session, 880_122, "Price tester")
            session.add_all([treasury, NatInventory(
                company_id=seller.id, item_id="steel", quantity=100,
                reserved_quantity=0, avg_cost_basis=10,
            )])
            await session.flush()

            ask = await MarketService.create_order(
                session, seller, "SELL", "steel", 500, 100, commit=False
            )
            assert ask.status == "ACTIVE"
            assert ask.state_advance_amount == 0
            assert ask.state_advance_reference_price == 100
            assert treasury.cash == 100_000
            book = await MarketService.get_orderbook(session, "steel")
            assert [point["price"] for point in book["history"]][-1] == 500
        await engine.dispose()

    asyncio.run(check())


def test_reversing_the_same_two_companies_does_not_create_a_second_price_pair() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            buyer = await _company(session, 880_125, "Single buyer")
            seller = await _company(session, 880_126, "Single seller")
            now = get_game_now()
            for index, (buyer_id, seller_id) in enumerate((
                (buyer.id, seller.id), (seller.id, buyer.id), (buyer.id, seller.id),
            )):
                session.add(NatMarketTrade(
                    buyer_company_id=buyer_id,
                    seller_company_id=seller_id,
                    item_id="steel",
                    price=100,
                    quantity=1,
                    total_amount=100,
                    fee_amount=0,
                    executed_at=now - timedelta(minutes=index),
                ))
            await session.flush()
            assert await MarketAdvanceService.reference_price(session, "steel", now=now) is None
        await engine.dispose()

    asyncio.run(check())


def test_no_trade_history_means_no_advance_and_self_trade_is_not_a_reference() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            seller = await _company(session, 880_130, "New seller")
            session.add(NatInventory(
                company_id=seller.id, item_id="steel", quantity=10,
                reserved_quantity=0, avg_cost_basis=1,
            ))
            await session.flush()
            # Old data may contain a self trade; it must not become a price reference.
            session.add(NatMarketTrade(
                buyer_company_id=seller.id,
                seller_company_id=seller.id,
                item_id="steel",
                price=900,
                quantity=1,
                total_amount=900,
                fee_amount=0,
                executed_at=get_game_now(),
            ))
            await session.flush()

            ask = await MarketService.create_order(
                session, seller, "SELL", "steel", 900, 1, commit=False
            )
            book = await MarketService.get_orderbook(session, "steel")
            assert ask.status == "ACTIVE"
            assert ask.state_advance_amount == 0
            assert book["history"] == []
        await engine.dispose()

    asyncio.run(check())


def test_unavailable_treasury_limits_advance_and_funded_order_cannot_be_cancelled() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            await _seed_external_trades(session)
            treasury = NatStateTreasury(id=1, cash=5_000)
            seller = await _company(session, 880_140, "Low treasury seller")
            session.add_all([treasury, NatInventory(
                company_id=seller.id, item_id="steel", quantity=100,
                reserved_quantity=0, avg_cost_basis=1,
            )])
            await session.flush()

            ask = await MarketService.create_order(
                session, seller, "SELL", "steel", 100, 100, commit=False
            )
            assert ask.state_advance_amount == 5_000
            assert ask.state_advance_quantity == 50
            assert treasury.cash == 0
            with pytest.raises(ValueError, match="аванс|профинанс"):
                await MarketService.cancel_order(session, seller, ask.id, commit=False)
        await engine.dispose()

    asyncio.run(check())


def test_company_reset_is_blocked_while_treasury_funded_goods_are_reserved() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            seller = await _company(session, 880_150, "Reset guarded")
            session.add(NatMarketOrder(
                company_id=seller.id, order_type="SELL", item_id="steel", price=100,
                quantity=10, remaining_qty=10, status="ACTIVE",
                state_advance_remaining_quantity=5,
            ))
            await session.flush()
            with pytest.raises(ValueError, match="сбросить компанию"):
                await CompanyService.reset_company_for_user(
                    session, seller.user_id, commit=False
                )
        await engine.dispose()

    asyncio.run(check())


def test_bankruptcy_preserves_funded_quantity_and_releases_only_unfunded_tail() -> None:
    async def check() -> None:
        engine, sessions = await _fixture()
        async with sessions() as session:
            seller = await _company(session, 880_160, "Collateral holder")
            inventory = NatInventory(
                company_id=seller.id, item_id="steel", quantity=100,
                reserved_quantity=100, avg_cost_basis=10,
            )
            order = NatMarketOrder(
                company_id=seller.id, order_type="SELL", item_id="steel", price=100,
                quantity=100, remaining_qty=100, status="ACTIVE",
                state_advance_remaining_quantity=30,
            )
            session.add_all([inventory, order])
            await session.flush()
            await MarketAdvanceService.preserve_collateral_during_bankruptcy(session, order)
            assert order.remaining_qty == 30
            assert inventory.reserved_quantity == 30
        await engine.dispose()

    asyncio.run(check())


def test_migration_adds_advance_columns_without_changing_existing_orders() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE nat_market_orders (id INTEGER PRIMARY KEY, status VARCHAR(20))"
            ))
            await connection.execute(text(
                "CREATE TABLE nat_market_trades (id INTEGER PRIMARY KEY, quantity FLOAT)"
            ))
            await connection.execute(text(
                "INSERT INTO nat_market_orders (id, status) VALUES (7, 'ACTIVE')"
            ))
            await _migrate_v21_state_market_advances(connection)
            row = (await connection.execute(text(
                "SELECT status, state_advance_amount, state_advance_remaining_quantity "
                "FROM nat_market_orders WHERE id=7"
            ))).one()
            assert row == ("ACTIVE", 0.0, 0.0)
            columns = (await connection.execute(text(
                "PRAGMA table_info('nat_market_trades')"
            ))).all()
            assert "state_repayment_amount" in {column[1] for column in columns}
        await engine.dispose()

    asyncio.run(check())


if __name__ == "__main__":
    test_state_advance_is_capped_and_market_sale_returns_funded_proceeds_to_treasury()
    test_funded_and_unfunded_parts_settle_to_their_respective_recipients()
    test_one_collusive_high_price_trade_does_not_raise_advance_reference()
    test_reversing_the_same_two_companies_does_not_create_a_second_price_pair()
    test_no_trade_history_means_no_advance_and_self_trade_is_not_a_reference()
    test_unavailable_treasury_limits_advance_and_funded_order_cannot_be_cancelled()
    test_company_reset_is_blocked_while_treasury_funded_goods_are_reserved()
    test_bankruptcy_preserves_funded_quantity_and_releases_only_unfunded_tail()
    test_migration_adds_advance_columns_without_changing_existing_orders()
    print("NATBIRZHA state advance checks: PASS")
