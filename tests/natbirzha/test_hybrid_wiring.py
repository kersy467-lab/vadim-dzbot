"""Hybrid production state has an upgrade-screen API and restart-safe schema."""

import asyncio

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.hybrid_merger_migration import (
    migrate_hybrid_mergers,
    migrate_hybrid_progress,
)
from backend.natbirzha.migrations import MIGRATIONS
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.hybrid_mergers import NatHybridMerger


def test_hybrid_migration_is_registered_and_repeatable() -> None:
    assert any(version == "natbirzha_v17_001_hybrid_mergers" for version, _ in MIGRATIONS)
    assert NatHybridMerger.__tablename__ == "nat_hybrid_mergers"

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(lambda sync: NatCompany.__table__.create(sync))
                await connection.run_sync(lambda sync: NatBusiness.__table__.create(sync))
                await migrate_hybrid_mergers(connection)
                await migrate_hybrid_mergers(connection)
                names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
                assert "nat_hybrid_mergers" in names
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_hybrid_api_routes_are_registered() -> None:
    paths = {route.path for route in natbirzha_router.routes}
    assert "/natbirzha/businesses/hybrids" in paths
    assert "/natbirzha/businesses/hybrids/open" in paths
    assert "/natbirzha/businesses/hybrids/{hybrid_id}/sell" in paths


def test_hybrid_progress_migration_preserves_existing_progress() -> None:
    assert any(version == "natbirzha_v45_001_hybrid_progress" for version, _ in MIGRATIONS)

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.execute(text(
                    "CREATE TABLE nat_businesses (id INTEGER PRIMARY KEY, stage INTEGER NOT NULL, updated_at DATETIME)"
                ))
                await connection.execute(text("""
                    CREATE TABLE nat_hybrid_mergers (
                        id INTEGER PRIMARY KEY, hybrid_business_id INTEGER,
                        source_a_stage INTEGER NOT NULL, source_b_stage INTEGER NOT NULL,
                        status TEXT NOT NULL
                    )
                """))
                await connection.execute(text(
                    "INSERT INTO nat_businesses (id, stage) VALUES (1, 1), (2, 4)"
                ))
                await connection.execute(text("""
                    INSERT INTO nat_hybrid_mergers
                        (id, hybrid_business_id, source_a_stage, source_b_stage, status)
                    VALUES (1, 1, 12, 8, 'ACTIVE'), (2, 2, 1, 1, 'ACTIVE')
                """))

                await migrate_hybrid_progress(connection)
                await migrate_hybrid_progress(connection)
                rows = await connection.execute(text(
                    "SELECT id, stage FROM nat_businesses ORDER BY id"
                ))
                assert rows.all() == [(1, 10), (2, 4)]
        finally:
            await engine.dispose()

    asyncio.run(check())
