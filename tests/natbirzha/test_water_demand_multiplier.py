"""Technical-water consumption increases while prices and supply output stay fixed."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory, get_item_base_price
from backend.natbirzha.services.building_catalog import get_building_spec
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.production_service import ProductionTickEngine


def test_water_inputs_are_multiplied_in_both_live_production_catalogs() -> None:
    factory_spec = get_building_spec("farm_grain")
    business_spec = get_business_spec("agroholding")
    water_utility = get_business_spec("water_utility")
    assert factory_spec is not None and factory_spec["inputs"]["water"] == 25
    assert business_spec is not None and business_spec["inputs_per_hour"]["water"] == 12.5
    assert business_spec["inputs_per_hour"]["energy"] == 0.25
    assert water_utility is not None and water_utility["outputs_per_hour"]["water"] == 12
    assert get_item_base_price("water") == 2


def test_factory_cycle_consumes_twenty_five_units_of_technical_water() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=830_001, name="Factory Water Demand", specialization="agrarian",
                level=1,
            )
            session.add(company)
            await session.flush()
            factory = NatFactory(
                company_id=company.id, building_type="farm_grain",
                specialization="agrarian", level=1,
            )
            water = NatInventory(company_id=company.id, item_id="water", quantity=24)
            energy = NatInventory(company_id=company.id, item_id="grid_quota", quantity=10)
            session.add_all([factory, water, energy])
            await session.commit()

            denied = await ProductionTickEngine.start_cycle(
                session, company, factory, now=datetime(2026, 9, 24, 12)
            )
            assert denied["success"] is False
            assert denied["reason"] == "insufficient_water"
            assert denied["needed"] == 25

            water.quantity = 25
            allowed = await ProductionTickEngine.start_cycle(
                session, company, factory, now=datetime(2026, 9, 24, 12)
            )
            assert allowed["success"] is True
            await session.refresh(water)
            assert water.quantity == 0

        await engine.dispose()

    asyncio.run(check())


def test_idle_business_consumes_scaled_hourly_water_demand() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 24, 12)
        async with sessions() as session:
            company = NatCompany(
                user_id=830_002, name="Idle Water Demand", specialization="agrarian", cash=20_000,
            )
            session.add(company)
            await session.flush()
            business = NatBusiness(
                company_id=company.id, business_type="agroholding", stage=1,
                status="ACTIVE", capital_invested=10_000,
                base_income_per_hour=0, base_maintenance_per_hour=14,
                last_settled_at=now,
            )
            water = NatInventory(
                company_id=company.id, item_id="water", quantity=25,
                avg_cost_basis=2,
            )
            energy = NatInventory(
                company_id=company.id, item_id="energy", quantity=100,
                avg_cost_basis=0,
            )
            session.add_all([business, water, energy])
            await session.commit()

            spec = get_business_spec("agroholding")
            assert spec is not None
            result = await IdleEconomyService._settle_resource_segment(
                session, company.id, business, spec, hours=2, upgrading=False,
            )
            await session.flush()
            await session.refresh(water)
            assert result[2] == 2
            assert result[3] == 50
            assert water.quantity == 0

        await engine.dispose()

    asyncio.run(check())
