"""Cycle input/output parity for the legacy NatFactory production system."""

import asyncio
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401 - register NATBIRZHA tables
from backend.natbirzha.migrations import MIGRATIONS
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.production_service import ProductionTickEngine


async def _create_solar_factory(session, *, company_spec: str = "power_engineer"):
    company = NatCompany(
        user_id=9_651_001,
        name=f"Cycle Multiplier {company_spec}",
        specialization=company_spec,
        level=60,
    )
    session.add(company)
    await session.flush()
    factory = NatFactory(
        company_id=company.id,
        building_type="solar_plant",
        specialization="power_engineer",
        level=1,
        workers=10,
    )
    grid = NatInventory(
        company_id=company.id,
        item_id="grid_quota",
        quantity=100.0,
        reserved_quantity=0.0,
    )
    session.add_all([factory, grid])
    await session.flush()
    return company, factory, grid


def test_maximum_legacy_bonuses_scale_inputs_with_actual_output() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 26, 12, 0, 0)
            company, factory, grid = await _create_solar_factory(session)
            factory.workers = 60  # +25% at the fifth workers tier
            factory.technology_level = 5  # +40%
            company.industry_upgrade_levels_json = {"power_engineer": 40}  # +200%
            await session.flush()

            started = await ProductionTickEngine.start_cycle(session, company, factory, now=now)
            assert started["success"] is True
            await session.refresh(factory)
            await session.refresh(grid)
            assert factory.cycle_output_multiplier == 5.25
            assert grid.quantity == 94.75

            completed = await ProductionTickEngine.complete_cycle(
                session, company, factory, now=now + timedelta(seconds=60),
            )
            assert completed["success"] is True
            assert completed["outputs_produced"] == {"energy": 78.75}

        await engine.dispose()

    asyncio.run(check())


def test_foreign_factory_efficiency_scales_inputs_and_outputs_equally() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 26, 12, 0, 0)
            company, factory, grid = await _create_solar_factory(session, company_spec="agrarian")
            efficiency = ProductionTickEngine.get_effective_efficiency(company, factory)

            started = await ProductionTickEngine.start_cycle(session, company, factory, now=now)
            assert started["success"] is True
            await session.refresh(factory)
            await session.refresh(grid)
            assert factory.cycle_output_multiplier == efficiency
            assert grid.quantity == round(100.0 - efficiency, 4)

            completed = await ProductionTickEngine.complete_cycle(
                session, company, factory, now=now + timedelta(seconds=60),
            )
            assert completed["success"] is True
            assert completed["outputs_produced"] == {"energy": round(15.0 * efficiency, 4)}

        await engine.dispose()

    asyncio.run(check())


def test_upgrades_during_a_running_cycle_do_not_change_its_multiplier() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 26, 12, 0, 0)
            company, factory, grid = await _create_solar_factory(session)

            started = await ProductionTickEngine.start_cycle(session, company, factory, now=now)
            assert started["success"] is True
            await session.refresh(factory)
            await session.refresh(grid)
            assert grid.quantity == 99.0

            factory.workers = 60
            factory.technology_level = 5
            company.industry_upgrade_levels_json = {"power_engineer": 40}
            await session.flush()

            completed = await ProductionTickEngine.complete_cycle(
                session, company, factory, now=now + timedelta(seconds=60),
            )
            assert completed["success"] is True
            assert completed["outputs_produced"] == {"energy": 15.0}

        await engine.dispose()

    asyncio.run(check())


def test_pre_migration_cycle_fallback_does_not_use_later_upgrades() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 26, 12, 0, 0)
            company, factory, _grid = await _create_solar_factory(session)
            started = await ProductionTickEngine.start_cycle(session, company, factory, now=now)
            assert started["success"] is True

            # Simulate an in-flight row from before the multiplier column existed,
            # with upgrades purchased after its base-level input was consumed.
            factory.cycle_output_multiplier = None
            factory.level = 5
            factory.workers = 60
            factory.technology_level = 5
            company.industry_upgrade_levels_json = {"power_engineer": 40}
            await session.flush()

            completed = await ProductionTickEngine.complete_cycle(
                session, company, factory, now=now + timedelta(seconds=60),
            )
            assert completed["success"] is True
            assert completed["outputs_produced"] == {"energy": 15.0}

        await engine.dispose()

    asyncio.run(check())


def test_legacy_cycle_multiplier_migration_is_registered_and_repeatable() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE nat_factories (id INTEGER PRIMARY KEY, current_recipe VARCHAR(100))"
            ))
            migration = dict(MIGRATIONS)["natbirzha_v12_001_factory_cycle_multiplier"]
            await migration(connection)
            await migration(connection)
            columns = {row[1] for row in (
                await connection.execute(text('PRAGMA table_info("nat_factories")'))
            ).all()}
        await engine.dispose()
        assert "cycle_output_multiplier" in columns

    assert "natbirzha_v12_001_factory_cycle_multiplier" in {version for version, _ in MIGRATIONS}
    asyncio.run(check())
