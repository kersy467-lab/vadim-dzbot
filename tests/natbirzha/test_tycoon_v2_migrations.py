"""Rollout controls and repeatable schema migration for NATBIRZHA 2.0."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.config import nat_settings
from backend.natbirzha.migrations import (
    MIGRATIONS,
    _migrate_v4_capacity_and_industry_boosts,
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
