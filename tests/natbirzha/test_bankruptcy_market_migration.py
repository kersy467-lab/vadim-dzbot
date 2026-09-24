"""Live databases receive bankruptcy tables and NPC cash counters once."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.migrations import MIGRATIONS, run_natbirzha_migrations


def test_bankruptcy_market_migration_is_registered_and_repeatable() -> None:
    versions = [version for version, _ in MIGRATIONS]
    assert "natbirzha_v7_001_bankruptcy_market" in versions

    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE nat_companies (id INTEGER PRIMARY KEY)"))
            await connection.execute(text("""
                CREATE TABLE nat_schema_versions (
                    version VARCHAR(80) PRIMARY KEY,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await connection.execute(text("""
                CREATE TABLE nat_npc_daily_volume (
                    id INTEGER PRIMARY KEY,
                    calendar_date DATE NOT NULL,
                    item_id VARCHAR(50) NOT NULL,
                    action VARCHAR(8) NOT NULL,
                    used_quantity FLOAT NOT NULL DEFAULT 0
                )
            """))
            await connection.execute(text("""
                INSERT INTO nat_npc_daily_volume
                (calendar_date, item_id, action, used_quantity)
                VALUES ('2026-09-24', 'energy', 'SELL', 1)
            """))
            for version, _ in MIGRATIONS[:-1]:
                await connection.execute(
                    text("INSERT INTO nat_schema_versions (version) VALUES (:version)"),
                    {"version": version},
                )
            await connection.execute(text("""
                CREATE TABLE nat_factories (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    building_type VARCHAR(100) NOT NULL,
                    specialization VARCHAR(50) NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1,
                    efficiency FLOAT NOT NULL DEFAULT 1.0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    workers INTEGER NOT NULL DEFAULT 10,
                    automation_level INTEGER NOT NULL DEFAULT 0,
                    automation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    automation_status VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
                    automation_pause_reason VARCHAR(80),
                    technology_level INTEGER NOT NULL DEFAULT 0,
                    current_recipe VARCHAR(100),
                    cycle_started_at TIMESTAMP,
                    cycle_ready_at TIMESTAMP,
                    cycle_input_cost FLOAT NOT NULL DEFAULT 0,
                    last_produced_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await run_natbirzha_migrations(connection)
            await run_natbirzha_migrations(connection)
            columns = {
                row[1] for row in (await connection.execute(text("PRAGMA table_info(nat_factories)"))).all()
            }
            npc_columns = {
                row[1] for row in (await connection.execute(text("PRAGMA table_info(nat_npc_daily_volume)"))).all()
            }
            initial_used_cash = await connection.scalar(text(
                "SELECT used_cash FROM nat_npc_daily_volume WHERE item_id='energy'"
            ))
            tables = {
                row[0] for row in (await connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )).all()
            }
            applied = await connection.scalar(text(
                "SELECT COUNT(*) FROM nat_schema_versions WHERE version='natbirzha_v7_001_bankruptcy_market'"
            ))
        await engine.dispose()
        assert "bankruptcy_acquired" in columns
        assert "used_cash" in npc_columns
        assert initial_used_cash == 0.0
        assert "nat_bankruptcy_market_lots" in tables
        assert applied == 1

    asyncio.run(run())


if __name__ == "__main__":
    test_bankruptcy_market_migration_is_registered_and_repeatable()
    print("Bankruptcy market migration checks: PASS")
