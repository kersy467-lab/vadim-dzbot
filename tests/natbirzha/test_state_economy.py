"""State Treasury reserve, fiscal default, and foreign export contract tests."""

import asyncio
import importlib

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select, text

from backend.db.models import Base
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


def test_new_treasury_uses_ten_trillion_reserve() -> None:
    assert StateTreasuryService.INITIAL_CASH == 10_000_000_000_000.0


def test_default_quote_widens_npc_spread() -> None:
    normal = NPCReserveService.get_npc_quote("energy")
    try:
        default = NPCReserveService.get_npc_quote("energy", default_mode=True)
    except TypeError:
        pytest.fail("NPC quotes must accept the Treasury default-mode policy")

    assert default["npc_buy_price"] == round(normal["npc_buy_price"] * 0.9, 2)
    assert default["npc_sell_price"] == round(normal["npc_sell_price"] * 1.1, 2)
    assert default["state_default_mode"] is True


def test_default_buyback_keeps_daily_cash_cap_but_adjusts_quantity() -> None:
    async def run() -> None:
        from backend.natbirzha.services.npc_service import NPCReserveService

        normal = await NPCReserveService.get_daily_quota(None, "water", "SELL")
        quote = NPCReserveService.get_npc_quote("water", default_mode=True)
        default = await NPCReserveService.get_daily_quota(
            None, "water", "SELL", npc_buy_price=quote["npc_buy_price"]
        )
        assert default["daily_quota_cash"] == normal["daily_quota_cash"]
        assert default["daily_quota_per_item"] > normal["daily_quota_per_item"]

    asyncio.run(run())


def test_default_mode_tax_is_thirty_percent_and_recovers_at_threshold() -> None:
    try:
        module = importlib.import_module("backend.natbirzha.services.state_economy_service")
    except ModuleNotFoundError:
        pytest.fail("State Economy policy service is missing")
    service = getattr(module, "StateEconomyService", None)
    assert service is not None, "State Economy policy service is missing"

    assert service.is_default_mode(999_999_999_999.99) is True
    assert service.is_default_mode(1_000_000_000_000.0) is False
    assert service.tax_rate(999_999_999_999.99, normal_rate=0.13) == 0.30
    assert service.tax_rate(1_000_000_000_000.0, normal_rate=0.13) == 0.13


def test_foreign_exports_sell_state_stock_once_per_cycle() -> None:
    async def run() -> None:
        models = importlib.import_module("backend.natbirzha.models.npc")
        stock_model = getattr(models, "NatStateReserveStock", None)
        assert stock_model is not None, "State stock model is missing"
        try:
            module = importlib.import_module("backend.natbirzha.services.state_economy_service")
        except ModuleNotFoundError:
            pytest.fail("State Economy policy service is missing")
        service = getattr(module, "StateEconomyService", None)
        assert service is not None, "State Economy policy service is missing"

        from datetime import datetime, timedelta
        from backend.natbirzha.models.creator import NatStateTreasury

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            treasury = NatStateTreasury(
                id=1, cash=5_000.0, foreign_exports_enabled=True,
                last_foreign_export_at=datetime(2026, 10, 9, 10, 0),
            )
            stock = stock_model(item_id="energy", quantity=100.0, average_cost_basis=8.0)
            session.add_all([treasury, stock])
            await session.commit()

            first = await service.run_foreign_export_cycle(
                session, now=datetime(2026, 10, 9, 10, 15), commit=False
            )
            assert first["quantity_sold"] == 10.0
            assert first["cash_received"] == 100.0
            assert treasury.cash == 5_100.0
            assert stock.quantity == 90.0

            duplicate = await service.run_foreign_export_cycle(
                session, now=datetime(2026, 10, 9, 10, 16), commit=False
            )
            assert duplicate["quantity_sold"] == 0.0
            assert treasury.cash == 5_100.0
        await engine.dispose()

    asyncio.run(run())


def test_default_export_cycle_and_empty_stock_do_not_create_cash() -> None:
    async def run() -> None:
        models = importlib.import_module("backend.natbirzha.models.npc")
        from backend.natbirzha.models.creator import NatStateTreasury
        service = importlib.import_module(
            "backend.natbirzha.services.state_economy_service"
        ).StateEconomyService
        from datetime import datetime

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            treasury = NatStateTreasury(
                id=1, cash=5_000.0, foreign_exports_enabled=False
            )
            stock = models.NatStateReserveStock(
                item_id="energy", quantity=100.0, average_cost_basis=8.0
            )
            session.add_all([treasury, stock])
            await session.commit()

            disabled = await service.run_foreign_export_cycle(
                session, now=datetime(2026, 10, 9, 10, 15), commit=False
            )
            assert disabled["quantity_sold"] == 0.0
            assert treasury.cash == 5_000.0 and stock.quantity == 100.0

            treasury.foreign_exports_enabled = True
            stock.quantity = 0.0
            empty = await service.run_foreign_export_cycle(
                session, now=datetime(2026, 10, 9, 10, 30), commit=False
            )
            assert empty["quantity_sold"] == 0.0
            assert empty["cash_received"] == 0.0
            assert treasury.cash == 5_000.0
        await engine.dispose()

    asyncio.run(run())


def test_treasury_reserve_migration_is_idempotent_and_preserves_larger_balance() -> None:
    async def run() -> None:
        from backend.natbirzha.migrations import _migrate_v26_state_treasury_economy

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE nat_state_treasury (id INTEGER PRIMARY KEY, cash FLOAT NOT NULL, updated_at TIMESTAMP NOT NULL)"
            ))
            await connection.execute(text(
                "INSERT INTO nat_state_treasury (id, cash, updated_at) VALUES (1, 5000, CURRENT_TIMESTAMP)"
            ))
            await _migrate_v26_state_treasury_economy(connection)
            assert await connection.scalar(text(
                "SELECT cash FROM nat_state_treasury WHERE id=1"
            )) == 10_000_000_000_000.0
            await connection.execute(text(
                "UPDATE nat_state_treasury SET cash=20000000000000 WHERE id=1"
            ))
            await _migrate_v26_state_treasury_economy(connection)
            assert await connection.scalar(text(
                "SELECT cash FROM nat_state_treasury WHERE id=1"
            )) == 20_000_000_000_000.0
            columns = await connection.execute(text('PRAGMA table_info("nat_state_treasury")'))
            assert {row[1] for row in columns.fetchall()} >= {
                "foreign_exports_enabled", "last_foreign_export_at"
            }
        await engine.dispose()

    asyncio.run(run())


def test_npc_buyback_cannot_overdraw_treasury() -> None:
    async def run() -> None:
        from backend.natbirzha.models.company import NatCompany
        from backend.natbirzha.models.inventory import NatInventory
        from backend.natbirzha.models.creator import NatStateTreasury
        from backend.natbirzha.services.npc_service import NPCReserveService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(
                user_id=910_123, name="No Reserve Corp", specialization="miner", cash=0.0
            )
            treasury = NatStateTreasury(id=1, cash=0.0)
            session.add_all([company, treasury])
            await session.flush()
            session.add(NatInventory(
                company_id=company.id, item_id="water", quantity=100.0,
                reserved_quantity=0.0, avg_cost_basis=1.0,
            ))
            await session.flush()
            result = await NPCReserveService.execute_npc_trade(
                session, company, "water", "SELL", 1.0
            )
            assert result["success"] is False
            assert result["reason"] == "treasury_insufficient_cash"
            assert treasury.cash == 0.0
            assert company.cash == 0.0
        await engine.dispose()

    asyncio.run(run())


def test_tax_liabilities_use_current_default_rate_and_keep_assessed_amount() -> None:
    async def run() -> None:
        from datetime import datetime, timedelta
        from backend.natbirzha.models.company import NatCompany
        from backend.natbirzha.models.creator import NatStateTreasury
        from backend.natbirzha.models.tax import NatCompanyProfitPeriod
        from backend.natbirzha.services.tax_service import TaxService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            start = datetime(2026, 10, 9, 0, 0)
            end = start + timedelta(hours=24)
            company = NatCompany(
                user_id=910_124, name="Tax Default Corp", specialization="miner", cash=0.0
            )
            treasury = NatStateTreasury(id=1, cash=999_999_999_999.0)
            session.add_all([company, treasury])
            await session.flush()
            session.add(NatCompanyProfitPeriod(
                company_id=company.id, period_start=start, period_end=end,
                realized_revenue=10_000.0, financial_income=0.0,
                cost_of_goods_sold=0.0, maintenance_expense=0.0,
                salary_expense=0.0, other_expenses=0.0,
            ))
            await session.flush()

            default_rows = await TaxService.sync_company(session, company.id, now=end)
            assert default_rows[0].principal == 3_000.0

            treasury.cash = 1_000_000_000_000.0
            next_end = end + timedelta(hours=24)
            session.add(NatCompanyProfitPeriod(
                company_id=company.id, period_start=end, period_end=next_end,
                realized_revenue=10_000.0, financial_income=0.0,
                cost_of_goods_sold=0.0, maintenance_expense=0.0,
                salary_expense=0.0, other_expenses=0.0,
            ))
            await session.flush()
            rows = await TaxService.sync_company(session, company.id, now=next_end)
            assert rows[0].principal == 3_000.0
            assert rows[1].principal == 1_300.0
            summary = await TaxService.summary(session, company.id, now=next_end)
            assert summary["rate_pct"] == 13.0
        await engine.dispose()

    asyncio.run(run())
