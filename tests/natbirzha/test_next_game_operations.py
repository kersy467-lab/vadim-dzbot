import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.db.models import Base
import backend.natbirzha.models
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_operations import (
    NatNextGameOperations, NatNextGameFactoryOperations, NatNextGameEmployee, NatNextGameVehicle,
)
from backend.natbirzha.next_game_catalog import find_next_game_branch
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_operations_service import NextGameOperationsService as Operations
from backend.natbirzha.services.next_game_operations_read import snapshot
from backend.natbirzha.api.next_game_mutation import mutate


@asynccontextmanager
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await Game.create_company(session, 981001, "Производитель")
        await Game.create_company(session, 981002, "Другой игрок")
        company = await Game._owned_company(session, 981001)
        treasury = await Game._treasury(session)
        company.sector_id, company.branch_path, company.level = "energy", ["thermal"], 60
        company.cash += 2000000.0051
        treasury.cash -= 2000000.0051
        factory = NatNextGameFacility(company_id=company.id, branch_id="thermal", level=10,
            next_cycle_at=datetime.utcnow() + timedelta(days=1))
        session.add(factory)
        for item in ("steel", "concrete", "electronics"):
            await Game._change_inventory(session, company.id, item, 100)
        await session.flush()
        await session.commit()
        yield session, company, factory
    await engine.dispose()


async def cash_total(session):
    await session.flush()
    treasury = await Game._treasury(session)
    return treasury.cash + (await session.scalar(select(func.sum(NatNextGameCompany.cash))))


def test_capacity_paid_with_real_cash_and_resources_and_retired_on_rebirth():
    async def check():
        async with database() as (session, company, facility):
            initial = await cash_total(session)
            assert await Operations.warehouse_capacity(session, company.id) == 100000
            assert await Operations.production_slots(session, company.id) == 12
            await Operations.operate(session, 981001, "WAREHOUSE")
            await Operations.operate(session, 981001, "LAND")
            assert await Operations.warehouse_capacity(session, company.id) == 150000
            assert await Operations.production_slots(session, company.id) == 16
            assert company.cash == pytest.approx(1965000.0051)
            assert (await Game._inventory_row(session, company.id, "steel")).quantity == 90
            assert (await Game._inventory_row(session, company.id, "concrete")).quantity == 80
            assert await cash_total(session) == pytest.approx(initial, rel=0, abs=1e-7)
            await Operations.retire_company(session, company.id)
            assert await Operations.warehouse_capacity(session, company.id) == 100000
            assert await Operations.production_slots(session, company.id) == 12
    asyncio.run(check())


def test_staff_automation_and_fuel_affect_separate_recipe_fields():
    async def check():
        async with database() as (session, company, facility):
            initial = await cash_total(session)
            await Operations.operate(session, 981001, "HIRE", facility.id, kind="process_engineer")
            await Operations.operate(session, 981001, "AUTOMATION", facility.id)
            await Operations.operate(session, 981001, "VEHICLE", facility.id, kind="delivery_van")
            base = find_next_game_branch("thermal")["factory"]
            original_inputs = dict(base["inputs"])
            recipe = await Operations.factory_recipe(session, company, facility, base)
            assert base["inputs"] == original_inputs
            assert recipe["output_quantity"] == pytest.approx(round(base["output_quantity"] * 1.05, 4))
            for item, amount in base["inputs"].items():
                if item != "fuel_diesel":
                    assert recipe["inputs"][item] == round(amount * .95, 4)
            assert recipe["inputs"]["fuel_diesel"] > base["inputs"].get("fuel_diesel", 0) * .95
            assert recipe["operating_cost"] == pytest.approx(base["operating_cost"] + 83 * base["cycle_seconds"] / 3600)
            assert await cash_total(session) == pytest.approx(initial, rel=0, abs=1e-7)
            with pytest.raises(ValueError, match="занята"):
                await Operations.operate(session, 981001, "HIRE", facility.id, kind="process_engineer")
    asyncio.run(check())


def test_ownership_prevents_hire_fire_repair_and_upgrade_of_foreign_factory():
    async def check():
        async with database() as (session, company, facility):
            await Operations.operate(session, 981001, "HIRE", facility.id, kind="process_engineer")
            await Operations.operate(session, 981001, "VEHICLE", facility.id, kind="delivery_van")
            person = await session.scalar(select(NatNextGameEmployee))
            vehicle = await session.scalar(select(NatNextGameVehicle))
            for action, asset in [("HIRE", None), ("AUTOMATION", None), ("LICENSE", None),
                                  ("FIRE", person.id), ("REPAIR", vehicle.id), ("SCRAP", vehicle.id)]:
                with pytest.raises(ValueError, match="Собственн|собственн"):
                    await Operations.operate(session, 981002, action, facility.id, asset, "process_engineer")
            assert (await session.get(NatNextGameVehicle, vehicle.id)).condition == 100
            assert await session.get(NatNextGameEmployee, person.id)
    asyncio.run(check())


def test_blocked_cycles_do_not_wear_fleet_and_completed_cycles_can_be_repaired():
    async def check():
        async with database() as (session, company, facility):
            await Operations.operate(session, 981001, "VEHICLE", facility.id, kind="delivery_van")
            vehicle = await session.scalar(select(NatNextGameVehicle))
            recipe = await Operations.factory_recipe(session, company, facility, find_next_game_branch("thermal")["factory"])
            assert await Game._cycle_block_reason(session, company, recipe)
            assert vehicle.condition == 100
            await Operations.complete_cycle(session, facility)
            assert vehicle.condition < 100
            before = await cash_total(session)
            await Operations.operate(session, 981001, "REPAIR", asset_id=vehicle.id)
            assert vehicle.condition == 100
            assert await cash_total(session) == pytest.approx(before, rel=0, abs=1e-7)
            vehicle.condition = 0
            without_fleet = await Operations.factory_recipe(session, company, facility, find_next_game_branch("thermal")["factory"])
            assert without_fleet["operations"]["fleet_bonus_pct"] == 0
            assert without_fleet["inputs"].get("fuel_diesel", 0) == find_next_game_branch("thermal")["factory"]["inputs"].get("fuel_diesel", 0)
    asyncio.run(check())


def test_license_is_paid_expires_and_rebirth_removes_all_factory_assets():
    async def check():
        async with database() as (session, company, facility):
            before = await cash_total(session)
            await Operations.operate(session, 981001, "LICENSE", facility.id)
            base = find_next_game_branch("thermal")["factory"]
            active = await Operations.factory_recipe(session, company, facility, base)
            expired = await Operations.factory_recipe(session, company, facility, base, now=datetime.utcnow() + timedelta(days=8))
            assert active["output_quantity"] == round(base["output_quantity"] * 1.1, 4)
            assert expired["output_quantity"] == base["output_quantity"]
            assert active["inputs"] == base["inputs"]
            assert await cash_total(session) == pytest.approx(before, rel=0, abs=1e-7)
            await Operations.operate(session, 981001, "HIRE", facility.id, kind="process_engineer")
            await Operations.operate(session, 981001, "VEHICLE", facility.id, kind="delivery_van")
            assert await Operations.has_factory_assets(session, facility.id)
            await Operations.retire_company(session, company.id)
            for model in (NatNextGameEmployee, NatNextGameVehicle, NatNextGameFactoryOperations, NatNextGameOperations):
                assert await session.scalar(select(func.count()).select_from(model)) == 0
    asyncio.run(check())


def test_route_transaction_replay_and_failed_resource_cost_are_atomic():
    async def check():
        async with database() as (session, company, facility):
            actor = SimpleNamespace(id=981001)
            payload = {"action": "WAREHOUSE"}
            async def command(): return await Operations.operate(session, 981001, "WAREHOUSE")
            first = await mutate(session, actor, "one-expansion", "/next-game/operations/actions", payload, command)
            replay = await mutate(session, actor, "one-expansion", "/next-game/operations/actions", payload, command)
            assert first == replay
            assert await Operations.warehouse_capacity(session, company.id) == 150000
            company_id, factory_id = company.id, facility.id
            electronics = await Game._inventory_row(session, company_id, "electronics")
            electronics.quantity = 0
            await session.commit()
            before = await cash_total(session)
            with pytest.raises(HTTPException) as caught:
                await mutate(session, actor, "missing-electronics", "/next-game/operations/actions",
                    {"action": "AUTOMATION"}, lambda: Operations.operate(session, 981001, "AUTOMATION", factory_id))
            assert caught.value.status_code == 400
            assert await cash_total(session) == pytest.approx(before, rel=0, abs=1e-7)
            assert await session.get(NatNextGameFactoryOperations, factory_id) is None
    asyncio.run(check())


def test_snapshot_has_actual_quotes_effects_and_owned_factories_only():
    async def check():
        async with database() as (session, company, facility):
            data = await snapshot(session, 981001)
            assert data["capacity"]["land_quote"]["cash"] == 25000
            assert data["capacity"]["warehouse_quote"]["inputs"] == {"concrete": 10, "steel": 5}
            assert data["facilities"][0]["id"] == facility.id
            assert data["facilities"][0]["license_quote"]["days"] == 7
            other = await snapshot(session, 981002)
            assert other["facilities"] == []
    asyncio.run(check())
