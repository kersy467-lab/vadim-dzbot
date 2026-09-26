"""Liquidity snapshots are discoverable, migrated and refreshed every half hour."""

import asyncio

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from backend.bot.services.liquidity_scheduler import register_liquidity_jobs
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.migrations import MIGRATIONS
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.liquidity import NatLiquiditySnapshot
from backend.natbirzha.liquidity_migration import migrate_liquidity_snapshots


def test_liquidity_snapshot_table_migration_is_repeatable() -> None:
    assert any(version == "natbirzha_v16_001_liquidity_snapshots" for version, _ in MIGRATIONS)
    assert NatLiquiditySnapshot.__tablename__ == "nat_liquidity_snapshots"

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(lambda sync: NatCompany.__table__.create(sync))
                await migrate_liquidity_snapshots(connection)
                await migrate_liquidity_snapshots(connection)
                names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
                assert "nat_liquidity_snapshots" in names
                indexes = await connection.run_sync(
                    lambda sync: {index["name"] for index in inspect(sync).get_indexes("nat_liquidity_snapshots")}
                )
                assert "uq_nat_liquidity_snapshot_window_end" in indexes
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_liquidity_api_and_half_hour_scheduler_are_registered() -> None:
    paths = {route.path for route in natbirzha_router.routes}
    assert "/natbirzha/market/liquidity" in paths

    class CaptureScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, function, **kwargs):
            self.jobs.append((function, kwargs))

    scheduler = CaptureScheduler()
    register_liquidity_jobs(scheduler)
    jobs = {options["id"]: options for _function, options in scheduler.jobs}
    refresh = jobs["natbirzha_liquidity_snapshot_job"]
    assert "minute='0,30'" in str(refresh["trigger"])
    assert refresh["replace_existing"] and refresh["coalesce"] and refresh["max_instances"] == 1
