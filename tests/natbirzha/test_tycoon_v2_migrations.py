"""Rollout controls and repeatable schema migration for NATBIRZHA 2.0."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.config import nat_settings
from backend.natbirzha.migrations import (
    MIGRATIONS,
    _migrate_v4_capacity_and_industry_boosts,
    _migrate_v13_realized_company_profit_tax,
    _migrate_v14_company_financial_income_tax,
    run_natbirzha_migrations,
)


def test_tycoon_v2_rollout_and_tax_migrations_are_registered() -> None:
    assert nat_settings.TYCOON_V2_ENABLED is True
    versions = [version for version, _ in MIGRATIONS]
    assert "natbirzha_v2_001_business_foundation" in versions
    assert "natbirzha_v2_002_daily_profit_tax" in versions
    assert "natbirzha_v4_capacity_industry_upgrades" in versions
    assert "natbirzha_v10_001_player_supply_deals" in versions
    assert "natbirzha_v11_001_tax_12h_periods" in versions
    assert "natbirzha_v13_001_realized_company_profit_tax" in versions
    assert "natbirzha_v14_001_company_financial_income_tax" in versions


def test_realized_profit_migration_freezes_existing_tax_liabilities() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE nat_companies (id INTEGER PRIMARY KEY)"))
            await connection.execute(text("INSERT INTO nat_companies (id) VALUES (1)"))
            await connection.execute(text("""
                CREATE TABLE nat_tax_periods (
                    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL,
                    period_start TIMESTAMP NOT NULL, period_end TIMESTAMP NOT NULL,
                    taxable_profit FLOAT NOT NULL, principal FLOAT NOT NULL,
                    penalty FLOAT NOT NULL, paid_amount FLOAT NOT NULL
                )
            """))
            await connection.execute(text("""
                INSERT INTO nat_tax_periods (
                    id, company_id, period_start, period_end, taxable_profit,
                    principal, penalty, paid_amount
                ) VALUES (1, 1, '2026-09-25 00:00:00', '2026-09-25 12:00:00', 500, 65, 3, 10)
            """))

            await _migrate_v13_realized_company_profit_tax(connection)
            await _migrate_v13_realized_company_profit_tax(connection)

            ledger = (await connection.execute(text("""
                SELECT legacy_taxable_profit FROM nat_company_profit_periods
                WHERE company_id=1 AND period_start='2026-09-25 00:00:00'
            """))).one()
            liability = (await connection.execute(text("""
                SELECT taxable_profit, principal, penalty, paid_amount
                FROM nat_tax_periods WHERE id=1
            """))).one()
            ledger_rows = await connection.scalar(text(
                "SELECT COUNT(*) FROM nat_company_profit_periods WHERE company_id=1"
            ))
        await engine.dispose()
        assert ledger.legacy_taxable_profit == 500
        assert tuple(liability) == (500, 65, 3, 10)
        assert ledger_rows == 1

    asyncio.run(check())


def test_financial_income_migration_is_repeatable_and_preserves_existing_rows() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("""
                CREATE TABLE nat_company_profit_periods (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    realized_revenue FLOAT NOT NULL DEFAULT 0
                )
            """))
            await connection.execute(text(
                "INSERT INTO nat_company_profit_periods (id, company_id, realized_revenue) VALUES (1, 9, 125)"
            ))
            await _migrate_v14_company_financial_income_tax(connection)
            await _migrate_v14_company_financial_income_tax(connection)
            columns = await connection.execute(text("PRAGMA table_info(nat_company_profit_periods)"))
            names = {row[1] for row in columns.fetchall()}
            row = (await connection.execute(text(
                "SELECT realized_revenue, financial_income FROM nat_company_profit_periods WHERE id=1"
            ))).one()
        await engine.dispose()
        assert "financial_income" in names
        assert tuple(row) == (125, 0)

    asyncio.run(check())


def test_tycoon_v2_business_foundation_migration_is_repeatable() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE nat_companies (id INTEGER PRIMARY KEY)"))
            await run_natbirzha_migrations(connection)
            await run_natbirzha_migrations(connection)

            tables = {
                row[0]
                for row in (await connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )).all()
            }
            migration_count = await connection.scalar(text(
                "SELECT COUNT(*) FROM nat_schema_versions "
                "WHERE version='natbirzha_v2_001_business_foundation'"
            ))

        await engine.dispose()
        assert {
            "nat_businesses", "nat_business_supply_policies", "nat_army_trainings", "nat_tax_daily",
            "nat_supply_deals", "nat_supply_deal_settlements",
        } <= tables
        assert migration_count == 1

    asyncio.run(check())


def test_capacity_migration_preserves_existing_level_and_territory_slots() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE nat_companies (id INTEGER PRIMARY KEY, level INTEGER NOT NULL, territory_tiles INTEGER NOT NULL)"
            ))
            await connection.execute(text(
                "INSERT INTO nat_companies (id, level, territory_tiles) VALUES (1, 30, 20)"
            ))
            await _migrate_v4_capacity_and_industry_boosts(connection)
            capacity = await connection.scalar(text(
                "SELECT business_slot_capacity FROM nat_companies WHERE id=1"
            ))
            industry_levels = await connection.scalar(text(
                "SELECT industry_upgrade_levels_json FROM nat_companies WHERE id=1"
            ))
        await engine.dispose()
        assert capacity == 39
        assert industry_levels == "{}"

    asyncio.run(check())


def test_instrument_migration_reconstructs_realized_pnl_from_old_trades() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE nat_companies (id INTEGER PRIMARY KEY, level INTEGER NOT NULL, territory_tiles INTEGER NOT NULL)"
            ))
            await connection.execute(text(
                "INSERT INTO nat_companies (id, level, territory_tiles) VALUES (1, 1, 0)"
            ))
            await connection.execute(text("""
                CREATE TABLE nat_instrument_trades (
                    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL,
                    instrument_code VARCHAR(12) NOT NULL, side VARCHAR(8) NOT NULL,
                    quantity FLOAT NOT NULL, gross_rub FLOAT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            """))
            for trade in (
                (1, 1, "GOLD", "buy", 10, 1010, "2026-01-01 00:00:00"),
                (2, 1, "GOLD", "buy", 10, 1000, "2026-01-02 00:00:00"),
                (3, 1, "GOLD", "sell", 5, 495, "2026-01-03 00:00:00"),
            ):
                await connection.execute(text("""
                    INSERT INTO nat_instrument_trades
                    (id, company_id, instrument_code, side, quantity, gross_rub, created_at)
                    VALUES (:id, :company_id, :instrument_code, :side, :quantity, :gross_rub, :created_at)
                """), {
                    "id": trade[0], "company_id": trade[1], "instrument_code": trade[2],
                    "side": trade[3], "quantity": trade[4], "gross_rub": trade[5],
                    "created_at": trade[6],
                })

            await _migrate_v4_capacity_and_industry_boosts(connection)
            result = (await connection.execute(text(
                "SELECT avg_cost_after_rub, realized_pnl_rub FROM nat_instrument_trades ORDER BY id"
            ))).all()

        await engine.dispose()
        assert result == [(101.0, 0.0), (100.5, 0.0), (100.5, -7.5)]

    asyncio.run(check())
