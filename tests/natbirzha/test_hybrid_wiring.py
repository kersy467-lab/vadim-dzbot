"""Hybrid production state has an upgrade-screen API and restart-safe schema."""

import asyncio

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.hybrid_merger_migration import migrate_hybrid_mergers
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
