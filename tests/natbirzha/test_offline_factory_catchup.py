"""Offline completion for opt-in automated legacy factories."""

import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.production_service import ProductionTickEngine


async def verify_locked_reads_refresh_stale_factory(sessions, start: datetime) -> None:
    async with sessions() as first_session:
        company = NatCompany(
            user_id=998002,
            name="Concurrent Factory",
            specialization="power_engineer",
            level=6,
            cash=1_000_000,
        )
        first_session.add(company)
        await first_session.flush()
        factory = NatFactory(
            company_id=company.id,
            building_type="solar_plant",
            specialization="power_engineer",
            level=1,
            workers=10,
            automation_level=1,
            automation_enabled=True,
            automation_status="IDLE",
        )
        first_session.add_all([
            factory,
            NatInventory(
                company_id=company.id,
                item_id="grid_quota",
                quantity=12,
                reserved_quantity=0,
                avg_cost_basis=0,
            ),
        ])
        await first_session.commit()
        await ProductionTickEngine.process_global_scheduled_tick(first_session, now=start)
        await first_session.refresh(factory)
        stale_deadline = factory.cycle_ready_at
        assert stale_deadline is not None

        later_deadline = stale_deadline + timedelta(minutes=5)
        async with sessions() as second_session:
            concurrent_factory = await second_session.get(NatFactory, factory.id)
            concurrent_factory.cycle_started_at = stale_deadline
            concurrent_factory.cycle_ready_at = later_deadline
            await second_session.commit()

        tick = await ProductionTickEngine.process_global_scheduled_tick(
            first_session,
            now=stale_deadline.replace(tzinfo=None) + timedelta(seconds=1),
        )
        assert tick["cycles_completed"] == 0
        await first_session.refresh(factory)
        assert factory.cycle_ready_at == later_deadline
        assert await first_session.scalar(select(NatInventory).where(
            NatInventory.company_id == company.id,
            NatInventory.item_id == "energy",
        )) is None


async def run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    start = datetime(2026, 9, 24, 10, 0, 0)
    async with sessions() as session:
        company = NatCompany(
            user_id=998001,
            name="Offline Factory",
            specialization="power_engineer",
            level=6,
            cash=1_000_000,
        )
        session.add(company)
        await session.flush()
        factory = NatFactory(
            company_id=company.id,
            building_type="solar_plant",
            specialization="power_engineer",
            level=1,
            workers=10,
            automation_level=1,
            automation_enabled=True,
            automation_status="IDLE",
        )
        session.add_all([
            factory,
            NatInventory(
                company_id=company.id,
                item_id="grid_quota",
                quantity=12,
                reserved_quantity=0,
                avg_cost_basis=0,
            ),
        ])
        await session.commit()
        company_id = company.id

        started = await ProductionTickEngine.process_global_scheduled_tick(session, now=start)
        assert started["cycles_started"] == 1
        await session.refresh(factory)
        ready_at = factory.cycle_ready_at.replace(tzinfo=None)
        assert start < ready_at <= start + timedelta(seconds=60)

        # The player doesn't reopen the Mini App for ten minutes. The saved
        # automation cursor should complete every elapsed cycle, not just one.
        completed = await ProductionTickEngine.catch_up_company(
            session, company_id, now=start + timedelta(minutes=10)
        )

        energy = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == company_id,
            NatInventory.item_id == "energy",
        ))
        assert len(completed) == 1
        assert completed[0]["completed_cycles"] >= 9
        assert energy is not None and energy.quantity >= 135
        await session.refresh(factory)
        assert factory.cycle_ready_at is not None
        assert factory.cycle_ready_at.replace(tzinfo=None) <= start + timedelta(minutes=11)

    await verify_locked_reads_refresh_stale_factory(sessions, start + timedelta(hours=1))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
    print("NATBIRZHA offline automated production checks: PASS")
