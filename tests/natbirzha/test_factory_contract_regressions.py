"""Regression coverage for production factories lost during V2 onboarding/reset."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401 - register NATBIRZHA tables
from backend.natbirzha.config import nat_settings
from backend.natbirzha.api.building_routes import get_buildings_catalog
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.migrations import MIGRATIONS
from backend.natbirzha.models.inventory import get_npc_buy_price, get_npc_sell_price
from backend.natbirzha.services.building_catalog import CANONICAL_BUILDINGS, get_building_spec
from backend.natbirzha.services.building_service import BuildingService
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.recipes import RECIPES, get_recipe, validate_recipe_graph


def test_new_company_keeps_starter_factory_when_tycoon_v2_is_enabled() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = await CompanyService.create_company(
                session,
                user_id=990_001,
                name="Factory Bootstrap Regression",
                specialization="agrarian",
            )
            factory = await session.scalar(
                select(NatFactory).where(NatFactory.company_id == company.id)
            )
            assert factory is not None, "Tycoon V2 onboarding dropped the legacy starter factory"
            assert factory.building_type == "farm_grain"
            assert factory.is_active is True

        await engine.dispose()

    assert nat_settings.TYCOON_V2_ENABLED is True
    asyncio.run(check())


def test_forester_is_a_first_class_specialization_with_logging_starter() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = await CompanyService.create_company(
                session,
                user_id=990_002,
                name="Forester Bootstrap Regression",
                specialization="forester",
            )
            factory = await session.scalar(
                select(NatFactory).where(NatFactory.company_id == company.id)
            )
            assert company.specialization == "forester"
            assert factory is not None and factory.building_type == "logging_camp"
            assert factory.specialization == "forester"

        await engine.dispose()

    asyncio.run(check())


def test_all_eight_factory_branches_bootstrap_their_canonical_starters() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        expected = (
            ("agrarian", "agrarian", "farm_grain"),
            ("miner", "miner", "iron_mine"),
            ("metallurgy", "metallurgist", "steel_mill"),
            ("oil_gas", "oilman", "oil_rig"),
            ("energy", "power_engineer", "solar_plant"),
            ("forester", "forester", "logging_camp"),
            ("chemist", "chemist", "chemical_plant"),
            ("technoprom", "technoprom", "component_factory"),
        )
        async with sessions() as session:
            for index, (alias, specialization, building_type) in enumerate(expected, 1):
                company = await CompanyService.create_company(
                    session,
                    user_id=991_000 + index,
                    name=f"Starter {specialization}",
                    specialization=alias,
                    commit=False,
                )
                factory = await session.scalar(
                    select(NatFactory).where(NatFactory.company_id == company.id)
                )
                spec = get_building_spec(building_type)
                assert company.specialization == specialization
                assert factory is not None and factory.building_type == building_type
                assert factory.specialization == specialization
                assert spec and spec["recipe_id"] in RECIPES

        await engine.dispose()

    asyncio.run(check())


def test_factory_repair_migration_backfills_only_companies_without_factories() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            missing = NatCompany(
                user_id=992_001,
                name="Missing Forestry Plant",
                specialization="forestry",
            )
            existing = NatCompany(
                user_id=992_002,
                name="Existing Oil Plant",
                specialization="oilman",
            )
            unknown = NatCompany(
                user_id=992_003,
                name="Unknown Legacy Industry",
                specialization="old_unknown_industry",
            )
            session.add_all([missing, existing, unknown])
            await session.flush()
            session.add(NatFactory(
                company_id=existing.id,
                building_type="oil_rig",
                specialization="oilman",
            ))
            await session.commit()

        async with engine.begin() as connection:
            repair_starters = dict(MIGRATIONS)["natbirzha_factory_001_restore_starters"]
            await repair_starters(connection)
            await repair_starters(connection)
            rows = (await connection.execute(
                select(NatFactory.company_id, NatFactory.building_type, NatFactory.specialization)
            )).all()

        assert len(rows) == 2
        assert (missing.id, "logging_camp", "forester") in rows
        assert any(row[0] == existing.id and row[1] == "oil_rig" for row in rows)
        assert all(row[0] != unknown.id for row in rows)
        await engine.dispose()

    versions = [version for version, _migration in MIGRATIONS]
    assert "natbirzha_factory_001_restore_starters" in versions
    asyncio.run(check())


def test_catalog_uses_server_npc_margin_and_marks_best_specialty_builds() -> None:
    company = NatCompany(
        user_id=993_001,
        name="Miner Profitability Estimate",
        specialization="miner",
        level=10,
        cash=500_000,
        territory_tiles=4,
        mastery_industry=10,
    )
    catalog = BuildingService.get_catalog_for_company(company, existing_count=0)
    mine = next(item for item in catalog if item["id"] == "iron_mine")
    spec = get_building_spec("iron_mine")
    assert spec is not None
    expected_revenue = sum(
        quantity * get_npc_buy_price(item_id)
        for item_id, quantity in spec["outputs"].items()
    )
    expected_input_cost = sum(
        quantity * get_npc_sell_price(item_id)
        for item_id, quantity in spec["inputs"].items()
    )
    expected_cycle_margin = round(expected_revenue - expected_input_cost, 2)

    assert mine["base_build_cost"] == spec["build_cost"]
    assert 0 < mine["build_cost"] < mine["base_build_cost"]
    assert mine["profitability"]["net_per_cycle"] == expected_cycle_margin
    assert mine["profitability"]["net_per_hour"] == round(
        expected_cycle_margin * 3600 / spec["cycle_duration"], 2
    )
    assert mine["recommended_for_specialization"] is True
    assert mine["recommendation_rank"] == 1
    assert mine["can_build"] is True

    no_slots = BuildingService.get_catalog_for_company(company, existing_count=4)
    blocked_mine = next(item for item in no_slots if item["id"] == "iron_mine")
    assert blocked_mine["can_build"] is False
    assert blocked_mine["status"] == "no_slots"


def test_catalog_endpoint_returns_server_slots_prices_and_license_access() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=993_003,
                name="Catalog Endpoint Regression",
                specialization="miner",
                level=60,
                cash=500_000,
                territory_tiles=4,
                mastery_industry=10,
            )
            session.add(company)
            await session.flush()

            response = await get_buildings_catalog(company, session)

        await engine.dispose()
        assert response["total"] == len(CANONICAL_BUILDINGS)
        assert response["factory_slots"] == {"used": 0, "max": 4, "free": 4}
        mine = next(item for item in response["catalog"] if item["id"] == "iron_mine")
        licensed_mine = next(item for item in response["catalog"] if item["id"] == "lithium_mine")
        assert mine["can_build"] is True
        assert mine["build_cost"] < mine["base_build_cost"]
        assert licensed_mine["required_license_active"] is False
        assert licensed_mine["status"] == "need_license"

    asyncio.run(check())


def test_build_service_always_deducts_the_authoritative_server_cost() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=993_002,
                name="Paid Factory Regression",
                specialization="agrarian",
                level=1,
                cash=100_000,
                territory_tiles=4,
            )
            session.add(company)
            await session.flush()
            original_cash = company.cash
            response = await BuildingService.build_factory(
                session, company, "farm_grain", commit=False
            )
            assert response["cost_paid"] == 15_000
            assert response["remaining_cash"] == original_cash - response["cost_paid"]
            assert company.cash == original_cash - response["cost_paid"]

        await engine.dispose()

    asyncio.run(check())


def test_canonical_catalog_contains_requested_factories_and_guards_dag() -> None:
    required = set("""
        farm_grain livestock_complex feed_mill food_factory bio_farm flour_mill
        iron_mine coal_mine copper_mine lithium_mine uranium_mine rare_earth_mine
        steel_mill rolling_mill machine_factory metal_structures_factory
        auto_components_factory superalloy_factory oil_rig gas_field refinery
        petrochemical_plant jet_fuel_plant plastics_factory solar_plant hydro_plant
        thermal_power_plant wind_farm nuclear_plant fusion_plant logging_camp sawmill
        pulp_mill cardboard_factory furniture_factory composite_factory chemical_plant
        fertilizer_plant polymer_factory electrolyte_factory biochem_factory
        catalyst_factory component_factory chip_factory server_factory robot_factory
        ai_factory aerospace_complex
    """.split())
    assert len(CANONICAL_BUILDINGS) >= 48
    assert required <= set(CANONICAL_BUILDINGS)
    assert len({spec["recipe_id"] for spec in CANONICAL_BUILDINGS.values()}) == len(CANONICAL_BUILDINGS)
    assert all(spec["recipe_id"] in RECIPES for spec in CANONICAL_BUILDINGS.values())
    assert validate_recipe_graph() is True

    RECIPES["regression_cycle"] = {
        "recipe_id": "regression_cycle",
        "factory_type": "test",
        "inputs": {"steel": 1},
        "outputs": {"iron_ore": 1},
    }
    try:
        try:
            get_recipe("farm_grain")
            assert False, "Production recipe lookup must reject a damaged graph"
        except ValueError as error:
            assert "cycle" in str(error).lower()
    finally:
        RECIPES.pop("regression_cycle", None)
