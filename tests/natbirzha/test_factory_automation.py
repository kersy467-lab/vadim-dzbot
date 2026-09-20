"""Persistent, opt-in factory automation without hidden resource purchases."""

import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.upgrade_service import UpgradeService


async def _create_power_factory(session, user_id: int, suffix: str, *, grid: float, energy: float = 0.0):
    company = NatCompany(
        user_id=user_id,
        name=f"Automation {suffix}",
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
    )
    session.add(factory)
    session.add_all([
        NatInventory(company_id=company.id, item_id="grid_quota", quantity=grid, reserved_quantity=0, avg_cost_basis=0),
        NatInventory(company_id=company.id, item_id="energy", quantity=energy, reserved_quantity=0, avg_cost_basis=0),
    ])
    await session.commit()
    return company, factory


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        company, factory = await _create_power_factory(session, 981001, "Gate", grid=5)
        assert factory.automation_enabled is False
        assert factory.automation_status == "MANUAL"
        assert factory.automation_pause_reason is None

        company.level = 5
        factory.automation_level = 0
        blocked = UpgradeService.describe(company, factory, "automation")
        assert blocked["allowed"] is False
        assert "6" in (blocked["reason"] or ""), "first automation tier must unlock at company level 6"
        company.level = 6
        unlocked = UpgradeService.describe(company, factory, "automation")
        assert unlocked["allowed"] is True
        assert unlocked["max_level"] == 10

        factory.automation_level = 1
        enabled = await ProductionTickEngine.set_automation(session, company, factory.id, True)
        assert enabled["success"] is True and enabled["automation_enabled"] is True
        await session.refresh(factory)
        assert factory.automation_enabled is True and factory.automation_status == "IDLE"
        disabled = await ProductionTickEngine.set_automation(session, company, factory.id, False)
        assert disabled["automation_enabled"] is False
        await session.commit()

    async with sessions() as session:
        company, factory = await _create_power_factory(session, 981002, "Loop", grid=3)
        factory.automation_enabled = True
        factory.automation_status = "IDLE"
        await session.commit()
        started_at = datetime(2026, 9, 19, 12, 0, 0)
        first_tick = await ProductionTickEngine.process_global_scheduled_tick(session, now=started_at)
        assert first_tick["cycles_started"] == 1 and first_tick["cycles_completed"] == 0
        await session.refresh(factory)
        assert factory.current_recipe == "generate_solar"
        assert factory.automation_status == "RUNNING"
        ready_at = factory.cycle_ready_at

        second_tick = await ProductionTickEngine.process_global_scheduled_tick(
            session, now=ready_at + timedelta(seconds=1)
        )
        assert second_tick["cycles_completed"] == 1 and second_tick["cycles_started"] == 1
        energy_row = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == company.id,
            NatInventory.item_id == "energy",
        ))
        grid_row = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == company.id,
            NatInventory.item_id == "grid_quota",
        ))
        assert energy_row.quantity == 15.0
        assert grid_row.quantity == 1.0

        duplicate_tick = await ProductionTickEngine.process_global_scheduled_tick(
            session, now=ready_at + timedelta(seconds=1)
        )
        await session.refresh(energy_row)
        await session.refresh(grid_row)
        assert duplicate_tick["cycles_completed"] == 0
        assert energy_row.quantity == 15.0 and grid_row.quantity == 1.0
        await ProductionTickEngine.set_automation(session, company, factory.id, False)
        await session.commit()

    async with sessions() as session:
        company, factory = await _create_power_factory(session, 981003, "Missing", grid=0)
        factory.automation_enabled = True
        factory.automation_status = "IDLE"
        await session.commit()
        tick = await ProductionTickEngine.process_global_scheduled_tick(
            session, now=datetime(2026, 9, 19, 13, 0, 0)
        )
        assert tick["cycles_started"] == 0
        await session.refresh(factory)
        assert factory.automation_status == "WAITING_INPUTS"
        assert factory.automation_pause_reason == "insufficient_grid_quota"
        assert factory.current_recipe is None

    async with sessions() as session:
        cap = float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
        company, factory = await _create_power_factory(session, 981004, "Overflow", grid=1, energy=cap - 10)
        factory.automation_enabled = True
        factory.automation_status = "IDLE"
        await session.commit()
        started_at = datetime(2026, 9, 19, 14, 0, 0)
        await ProductionTickEngine.process_global_scheduled_tick(session, now=started_at)
        await session.refresh(factory)
        ready_at = factory.cycle_ready_at
        tick = await ProductionTickEngine.process_global_scheduled_tick(
            session, now=ready_at + timedelta(seconds=1)
        )
        assert tick["cycles_completed"] == 0
        await session.refresh(factory)
        energy_row = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == company.id,
            NatInventory.item_id == "energy",
        ))
        assert energy_row.quantity == cap - 10
        assert factory.current_recipe == "generate_solar", "overflow must keep the completed cycle collectible"
        assert factory.automation_status == "WAITING_COLLECTION"
        assert factory.automation_pause_reason == "inventory_overflow"

    await engine.dispose()
    print("NATBIRZHA factory automation checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
