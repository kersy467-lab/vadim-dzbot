"""Existing databases receive the independent state share tables once."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.migrations import MIGRATIONS, run_natbirzha_migrations


def test_state_share_schema_migration_is_registered_and_repeatable() -> None:
    versions = [version for version, _ in MIGRATIONS]
    assert "natbirzha_v3_001_state_shares" in versions

    async def run() -> None:
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
            applied = await connection.scalar(text(
                "SELECT COUNT(*) FROM nat_schema_versions WHERE version='natbirzha_v3_001_state_shares'"
            ))
        await engine.dispose()
        assert {
            "nat_state_shares",
            "nat_state_share_holdings",
            "nat_state_share_operations",
            "nat_state_share_daily_settlements",
            "nat_state_share_dividend_payments",
        } <= tables
        assert applied == 1

    asyncio.run(run())


if __name__ == "__main__":
    test_state_share_schema_migration_is_registered_and_repeatable()
    print("NATBIRZHA state share migration checks: PASS")
