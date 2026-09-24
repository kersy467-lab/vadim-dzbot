"""Contract tests for alternate timed steel-making routes."""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.building_catalog import CANONICAL_BUILDINGS
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.recipes import RECIPES, get_recipe_for_factory, validate_recipe_graph


def _input_value(recipe: dict[str, object]) -> float:
    return sum(
        float(quantity) * float(CANONICAL_ITEMS[item_id]["base_price"])
        for item_id, quantity in recipe["inputs"].items()
    )


def test_steel_mill_alternate_recipes_are_balanced_and_keep_standard_default() -> None:
    building = CANONICAL_BUILDINGS["steel_mill"]
    default_id = building["recipe_id"]
    standard = RECIPES[default_id]

    assert default_id == "smelt_steel_mill"
    assert get_recipe_for_factory("steel_mill")["recipe_id"] == default_id
    assert standard["inputs"] == {"iron_ore": 2.0, "coal": 1.0, "energy": 4.0}
    assert standard["outputs"] == {"steel": 1.5}
    assert standard["energy_cost"] == 4

    electric = RECIPES["smelt_steel_electric"]
    coal_heavy = RECIPES["smelt_steel_coal_heavy"]
    for recipe in (electric, coal_heavy):
        assert recipe["factory_type"] == "steel_mill"
        assert recipe["specialization"] == "metallurgist"
        assert recipe["outputs"] == standard["outputs"]
        assert recipe["duration"] == standard["duration"]
        assert recipe["labor_demand"] == standard["labor_demand"]
        assert recipe["level_req"] == standard["level_req"]
        assert _input_value(recipe) == _input_value(standard)

    assert electric["inputs"] == {"iron_ore": 2.0, "energy": 7.0}
    assert coal_heavy["inputs"] == {"iron_ore": 2.0, "coal": 2.0, "energy": 1.0}
    assert electric["name"] == "Электроплавка без угля"
    assert coal_heavy["name"] == "Угольная плавка (экономия энергии)"
    assert electric["energy_cost"] == 7
    assert coal_heavy["energy_cost"] == 1
    assert validate_recipe_graph() is True


def test_alternate_recipe_ids_are_unique_and_use_canonical_items() -> None:
    assert len(RECIPES) == len({recipe["recipe_id"] for recipe in RECIPES.values()})
    for recipe in RECIPES.values():
        assert set(recipe["inputs"]) <= set(CANONICAL_ITEMS)
        assert set(recipe["outputs"]) <= set(CANONICAL_ITEMS)


def test_selected_electric_recipe_starts_without_coal_and_spends_its_inputs() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 24, 12, 0, 0)
            company = NatCompany(
                user_id=981120, name="Steel Test", specialization="metallurgist",
                level=1, xp=0, cash=100_000, territory_tiles=4,
                created_at=now, updated_at=now,
            )
            session.add(company)
            await session.flush()
            factory = NatFactory(
                company_id=company.id, building_type="steel_mill",
                specialization="metallurgist", level=1, workers=35,
                is_active=True, created_at=now,
            )
            ore = NatInventory(company_id=company.id, item_id="iron_ore", quantity=4)
            energy = NatInventory(company_id=company.id, item_id="energy", quantity=10)
            session.add_all([factory, ore, energy])
            await session.flush()

            result = await ProductionTickEngine.start_cycle(
                session, company, factory, "smelt_steel_electric", now=now,
            )
            assert result["success"] is True
            await session.refresh(factory)
            await session.refresh(ore)
            await session.refresh(energy)
            assert factory.current_recipe == "smelt_steel_electric"
            assert ore.quantity == 2
            assert energy.quantity == 3
            coal = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id, NatInventory.item_id == "coal",
            ))
            assert coal is None

        await engine.dispose()

    asyncio.run(run())
