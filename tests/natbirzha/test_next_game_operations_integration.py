import asyncio
from datetime import datetime, timedelta
import pytest
from sqlalchemy import func, select
from test_next_game_operations import database, cash_total
from backend.natbirzha.models.next_game import NatNextGameFacility
from backend.natbirzha.models.next_game_operations import NatNextGameVehicle, NatNextGameFactoryOperations, NatNextGameEmployee
from backend.natbirzha.models.next_game_civic import NatNextGameEconomicEvent, NatNextGameCityOrder
from backend.natbirzha.next_game_catalog import get_next_game_catalog, find_next_game_branch
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_service.common import facility_recipe_at_level
from backend.natbirzha.services.next_game_operations_service import NextGameOperationsService as Operations
from backend.natbirzha.services.next_game_market_service import NextGameMarketService as Market
from backend.natbirzha.services.next_game_community_service import NextGameCommunityService as Aid
from backend.natbirzha.services.next_game_admin_service import NextGameAdminService as Admin
from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService as Fusion
from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService as Progression


def test_real_completed_cycle_pays_salary_consumes_diesel_wears_fleet_and_snapshot_matches():
    async def check():
        async with database() as (session, company, facility):
            await Operations.operate(session, 981001, "HIRE", facility.id, kind="process_engineer")
            await Operations.operate(session, 981001, "VEHICLE", facility.id, kind="delivery_van")
            await Operations.operate(session, 981001, "AUTOMATION", facility.id)
            base = facility_recipe_at_level(find_next_game_branch("thermal")["factory"], facility.level)
            expected = await Operations.factory_recipe(session, company, facility, base)
            for item, quantity in expected["inputs"].items():
                await Game._change_inventory(session, company.id, item, quantity * 2)
            before_cash = company.cash
            before_total = await cash_total(session)
            fuel = (await Game._inventory_row(session, company.id, "fuel_diesel")).quantity
            current = datetime.utcnow()
            facility.next_cycle_at = current
            result = await Game.settle_company(session, 981001, now=current)
            assert result["cycles_completed"] == 1
            assert company.cash == pytest.approx(before_cash - expected["operating_cost"], abs=1e-7)
            assert await cash_total(session) == pytest.approx(before_total, rel=0, abs=1e-7)
            assert (await Game._inventory_row(session, company.id, "fuel_diesel")).quantity == pytest.approx(round(fuel - expected["inputs"]["fuel_diesel"], 4))
            assert (await Game._inventory_row(session, company.id, base["output_item"])).quantity == expected["output_quantity"]
            vehicle = await session.scalar(select(NatNextGameVehicle))
            condition = vehicle.condition
            assert condition < 100
            snap = await Game.snapshot(session, 981001, now=current, section="overview")
            assert snap["facilities"][0]["recipe"]["operations"]["input_saving_pct"] == 5
            assert "fuel_diesel" in {row["item_id"] for row in snap["market"]}
            assert snap["production"]["operating_cash_per_hour"] > base["operating_cost"] * 3600 / base["cycle_seconds"]
            assert vehicle.condition == condition
    asyncio.run(check())


def test_expanded_warehouse_is_respected_by_npc_market_aid_and_admin():
    async def check():
        async with database() as (session, company, facility):
            await Operations.operate(session, 981001, "WAREHOUSE")
            await Game._change_inventory(session, company.id, "water", 99999)
            await Game.trade(session, 981001, "water", "BUY", 2)
            seller = await Game._owned_company(session, 981002)
            await Game._change_inventory(session, seller.id, "water", 10)
            await Market.create_limit_order(session, 981002, "water", "SELL", 1, 2)
            fill = await Market.create_limit_order(session, 981001, "water", "BUY", 1, 2)
            assert fill["executed_quantity"] == 1
            request = await Aid.create_request(session, 981001, "water", 100001, "Большой склад")
            await Aid.donate(session, 981002, request["request_id"], 1)
            await Admin.operate(session, 981001, "ITEM_GRANT", company.id, 1, "water", "Проверка склада")
            assert (await Game._inventory_row(session, company.id, "water")).quantity == 100004
            await Game._change_inventory(session, company.id, "water", 49996)
            with pytest.raises(ValueError, match="места"):
                await Game.trade(session, 981001, "water", "BUY", 1)
            with pytest.raises(ValueError, match="заполнен"):
                await Admin.operate(session, 981001, "ITEM_GRANT", company.id, 1, "water", "Нельзя переполнить")
    asyncio.run(check())


def test_build_slots_block_then_paid_land_unlocks_and_city_cash_is_reserved():
    async def check():
        async with database() as (session, company, facility):
            branches = [b["id"] for sector in get_next_game_catalog() for b in sector["branches"] if b["id"] != "thermal"]
            company.branch_path = ["thermal", *branches[:12]]
            for branch in branches[:11]:
                session.add(NatNextGameFacility(company_id=company.id, branch_id=branch, level=1,
                    next_cycle_at=datetime.utcnow() + timedelta(days=1)))
            await session.flush()
            with pytest.raises(ValueError, match="места"):
                await Game.build_facility(session, 981001, branch_id=branches[11])
            await Operations.operate(session, 981001, "LAND")
            await Game.build_facility(session, 981001, branch_id=branches[11])
            assert await session.scalar(select(func.count(NatNextGameFacility.id)).where(NatNextGameFacility.company_id == company.id)) == 13
            treasury = await Game._treasury(session)
            available = await Game._available_treasury_cash(session, treasury)
            current = datetime.utcnow()
            session.add(NatNextGameCityOrder(item_id="water", unit_price=2, quantity=100,
                remaining_quantity=100, rotation_at=current, expires_at=current + timedelta(hours=3), status="OPEN"))
            await session.flush()
            assert await Game._available_treasury_cash(session, treasury) == pytest.approx(available - 200)
    asyncio.run(check())


def test_sector_event_changes_real_output_and_read_recipe_together():
    async def check():
        async with database() as (session, company, facility):
            base = facility_recipe_at_level(find_next_game_branch("thermal")["factory"], facility.level)
            for item, quantity in base["inputs"].items():
                await Game._change_inventory(session, company.id, item, quantity * 2)
            now = datetime.utcnow()
            session.add(NatNextGameEconomicEvent(sector_id="energy", starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=1), creator_tg_id=981001))
            await session.flush()
            facility.next_cycle_at = now
            assert (await Game.settle_company(session, 981001, now=now))["cycles_completed"] == 1
            expected = round(base["output_quantity"] * 1.25, 4)
            assert (await Game._inventory_row(session, company.id, base["output_item"])).quantity == expected
            snap = await Game.snapshot(session, 981001, now=now, section="overview")
            assert snap["facilities"][0]["recipe"]["output_quantity"] == expected
    asyncio.run(check())


def test_fusion_rejects_paid_source_assets_and_dissolve_preserves_complex_staff():
    async def check():
        async with database() as (session, company, facility):
            company.branch_path = ["thermal", "renewables"]
            second = NatNextGameFacility(company_id=company.id, branch_id="renewables", level=5,
                next_cycle_at=datetime.utcnow() + timedelta(days=1))
            session.add(second)
            await session.flush()
            await Operations.operate(session, 981001, "HIRE", facility.id, kind="process_engineer")
            with pytest.raises(ValueError, match="штат"):
                await Fusion.fuse(session, 981001, [facility.id, second.id])
            person = await session.scalar(select(NatNextGameEmployee))
            await Operations.operate(session, 981001, "FIRE", asset_id=person.id)
            result = await Fusion.fuse(session, 981001, [facility.id, second.id])
            complex_row = await session.scalar(select(NatNextGameFacility).where(NatNextGameFacility.company_id == company.id))
            await Operations.operate(session, 981001, "HIRE", complex_row.id, kind="process_engineer")
            await Operations.operate(session, 981001, "AUTOMATION", complex_row.id)
            snap = await Game.snapshot(session, 981001, section="overview")
            assert set(snap["consumed_branch_ids"]) == {"thermal", "renewables"}
            await Fusion.dissolve(session, 981001, result["merger_id"])
            person = await session.scalar(select(NatNextGameEmployee))
            settings = await session.scalar(select(NatNextGameFactoryOperations))
            assert person and settings and settings.automation_level == 1
            assert person.facility_id == settings.facility_id
            assert await session.get(NatNextGameFacility, person.facility_id)
    asyncio.run(check())


def test_real_rebirth_clears_paid_assets_and_capacity_without_creating_cash():
    async def check():
        async with database() as (session, company, facility):
            await Operations.operate(session, 981001, "HIRE", facility.id, kind="process_engineer")
            await Operations.operate(session, 981001, "VEHICLE", facility.id, kind="delivery_van")
            await Operations.operate(session, 981001, "WAREHOUSE")
            await Operations.operate(session, 981001, "LAND")
            company.branch_path = ["thermal", "power_exchange"]
            session.add(NatNextGameFacility(company_id=company.id, branch_id="power_exchange", level=1,
                next_cycle_at=datetime.utcnow() + timedelta(days=1)))
            await session.flush()
            before = await cash_total(session)
            await Progression.rebirth(session, 981001, confirm=True)
            assert await cash_total(session) == pytest.approx(before, rel=0, abs=1e-7)
            assert await Operations.warehouse_capacity(session, company.id) == 100000
            assert await Operations.production_slots(session, company.id) == 12
            assert await session.scalar(select(func.count()).select_from(NatNextGameEmployee)) == 0
            assert await session.scalar(select(func.count()).select_from(NatNextGameVehicle)) == 0
    asyncio.run(check())


def test_catchup_cycles_before_event_start_do_not_receive_new_event_bonus():
    async def check():
        async with database() as (session, company, facility):
            base = facility_recipe_at_level(find_next_game_branch("thermal")["factory"], facility.level)
            for item, quantity in base["inputs"].items():
                await Game._change_inventory(session, company.id, item, quantity * 2)
            now = datetime.utcnow()
            due = now - timedelta(seconds=base["cycle_seconds"])
            session.add(NatNextGameEconomicEvent(sector_id="energy", starts_at=now,
                ends_at=now + timedelta(hours=1), creator_tg_id=981001))
            await session.flush()
            facility.next_cycle_at = due
            assert (await Game.settle_company(session, 981001, now=now))["cycles_completed"] == 2
            assert (await Game._inventory_row(session, company.id, base["output_item"])).quantity == (
                base["output_quantity"] + round(base["output_quantity"] * 1.25, 4))
    asyncio.run(check())
