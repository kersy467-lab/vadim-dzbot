"""Rollout controls and repeatable schema migration for NATBIRZHA 2.0."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.config import nat_settings
from backend.natbirzha.migrations import MIGRATIONS, run_natbirzha_migrations


def test_tycoon_v2_is_disabled_until_creator_rollout() -> None:
    assert nat_settings.TYCOON_V2_ENABLED is False
    assert "natbirzha_v2_001_business_foundation" in [version for version, _ in MIGRATIONS]


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
        assert {"nat_businesses", "nat_business_supply_policies", "nat_army_trainings"} <= tables
        assert migration_count == 1

    asyncio.run(check())
