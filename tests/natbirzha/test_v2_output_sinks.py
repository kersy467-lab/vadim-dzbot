"""Every V2 career output needs a real recipe or atomic purchase sink."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.army_service import RECRUITMENT_CATALOG
from backend.natbirzha.services.business_asset_catalog import PROJECT_CATALOG
from backend.natbirzha.services.business_asset_service import BusinessAssetService
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


RECURRING_CATALOG_SINKS = {
    "aluminum": "electrical_factory",
    "bio_raw": "high_purity_reagents",
    "bioreagent": "greenhouse_v2",
    "cardboard": "courier_service_v2",
    "composite": "synthetic_materials",
    "electrolyte": "battery_system_factory",
    "fresh_food": "food_processing_v2",
    "gasoline": "courier_service_v2",
    "industrial_gases": "microelectronics_complex",
    "lng": "small_gas_chp",
    "silver_ore": "electronics_workshop",
    "sugar_raw": "food_processing_v2",
}


def test_every_v2_career_output_has_a_business_project_or_army_sink() -> None:
    produced = {
        item_id
        for spec in CAREER_BUSINESSES.values()
        for item_id in spec["outputs_per_hour"]
    }
    consumed = {
        item_id
        for spec in CAREER_BUSINESSES.values()
        for item_id in spec["inputs_per_hour"]
    }
    consumed.update(
        item_id
        for spec in CAREER_BUSINESSES.values()
        for item_id in spec.get("open_resources", {})
    )
    consumed.update(
        item_id
        for spec in CAREER_BUSINESSES.values()
        for milestone in spec["milestones"].values()
        for item_id in milestone.get("resources", {})
    )
    consumed.update(
        item_id for spec in PROJECT_CATALOG.values() for item_id in spec["inputs"]
    )
    consumed.update(
        item_id
        for spec in RECRUITMENT_CATALOG.values()
        for item_id in spec["items"]
    )

    assert not produced - consumed, sorted(produced - consumed)


def test_existing_business_projects_debit_the_new_v2_sink_items() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        project_inputs = {
            project_type: {
                item_id: quantity
                for item_id, quantity in spec["inputs"].items()
                if item_id in {
                    "brick", "cardboard", "construction_capacity", "diamonds",
                    "furniture", "industrial_gases", "prefab_modules", "silver_ore",
                    "electrical_equipment", "ai_accelerator", "quantum_modules", "robots",
                    "advanced_alloy", "advanced_composite", "titanium_alloy",
                }
            }
            for project_type, spec in PROJECT_CATALOG.items()
        }
        project_inputs = {key: value for key, value in project_inputs.items() if value}
        assert project_inputs

        async with sessions() as session:
            for index, (project_type, spec) in enumerate(PROJECT_CATALOG.items(), start=1):
                required_sinks = project_inputs.get(project_type, {})
                if not required_sinks:
                    continue
                specialization = spec["specializations"][0]
                company = NatCompany(
                    user_id=982_000 + index,
                    name=f"Project Sink {index}",
                    specialization=specialization,
                    cash=2_000_000,
                )
                session.add(company)
                await session.flush()
                business = NatBusiness(
                    company_id=company.id,
                    business_type=f"test_{project_type}",
                    specialization=specialization,
                    stage=int(spec["min_stage"]),
                )
                session.add(business)
                inventories = {
                    item_id: NatInventory(
                        company_id=company.id,
                        item_id=item_id,
                        quantity=float(quantity) + 1.0,
                    )
                    for item_id, quantity in spec["inputs"].items()
                }
                session.add_all(inventories.values())
                await session.flush()

                await BusinessAssetService.start_project(
                    session,
                    company.id,
                    business.id,
                    project_type,
                    now=datetime(2026, 9, 26, 12),
                )
                for item_id, quantity in required_sinks.items():
                    assert inventories[item_id].quantity == 1.0

        await engine.dispose()

    asyncio.run(check())


def test_recurring_v2_recipe_sinks_consume_inventory_during_settlement() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        start = datetime(2026, 9, 26, 12)
        async with sessions() as session:
            for index, (item_id, business_type) in enumerate(
                RECURRING_CATALOG_SINKS.items(), start=1
            ):
                spec = CAREER_BUSINESSES[business_type]
                assert float(spec["inputs_per_hour"].get(item_id, 0)) > 0
                company = NatCompany(
                    user_id=983_000 + index,
                    name=f"Recurring Sink {index}",
                    specialization=spec["specialization"],
                    cash=100_000_000,
                )
                session.add(company)
                await session.flush()
                business = NatBusiness(
                    company_id=company.id,
                    business_type=business_type,
                    specialization=spec["specialization"],
                    stage=1,
                    base_maintenance_per_hour=spec["base_maintenance_per_hour"],
                    last_settled_at=start,
                )
                session.add(business)
                await session.flush()
                rates = resource_business_rates(business, spec, upgrading=False)
                inventories = {
                    required_item: NatInventory(
                        company_id=company.id,
                        item_id=required_item,
                        quantity=max(100.0, float(quantity) * rates.input_multiplier * 2),
                    )
                    for required_item, quantity in spec["inputs_per_hour"].items()
                }
                session.add_all(inventories.values())
                await session.flush()

                previous_quantity = inventories[item_id].quantity
                settled = await IdleEconomyService.settle_company(
                    session,
                    company.id,
                    now=start + timedelta(hours=1),
                )
                expected_consumption = (
                    float(spec["inputs_per_hour"][item_id])
                    * rates.input_multiplier
                    * settled["settled_hours"]
                )
                assert settled["settled_hours"] == 1
                assert inventories[item_id].quantity == pytest.approx(
                    previous_quantity - expected_consumption,
                    abs=1e-5,
                )

        await engine.dispose()

    asyncio.run(check())
