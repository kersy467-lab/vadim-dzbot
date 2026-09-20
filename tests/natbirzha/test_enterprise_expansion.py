import os
import sys
import pytest
import asyncio
from datetime import datetime, timedelta

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.db.session import init_db, async_session_factory
from backend.natbirzha.config import nat_settings, get_game_now
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.company_service import CompanyService, STARTER_FACTORIES
from backend.natbirzha.services.building_catalog import (
    CANONICAL_BUILDINGS, get_building_spec, list_catalog_for_company, resolve_building_type
)
from backend.natbirzha.services.recipes import RECIPES, validate_recipe_dag
from backend.natbirzha.services.building_service import BuildingService
from backend.natbirzha.services.production_service import ProductionTickEngine

async def run_all_expansion_tests():
    print("\n" + "=" * 64)
    print("🏭 RUNNING 31-POINT ENTERPRISE EXPANSION TEST SUITE (§25)")
    print("=" * 64)

    await init_db()

    import time
    import random
    base_uid = int(time.time() * 1000) % 70000000 + random.randint(10000, 99999)

    # 1-8: Starter factory mapping for all 8 specializations
    print("\n--- [1-8/31] Testing All 8 Starter Specialization Factory Mappings ---")
    starter_expected = [
        ("oil_gas", "oilman", "oil_rig"),
        ("metallurgy", "metallurgist", "steel_mill"),
        ("energy", "power_engineer", "solar_plant"),
        ("agrarian", "agrarian", "farm_grain"),
        ("miner", "miner", "iron_mine"),
        ("forester", "forester", "logging_camp"),
        ("chemist", "chemist", "chemical_plant"),
        ("technoprom", "technoprom", "component_factory"),
    ]
    async with async_session_factory() as session:
        for idx, (alias, spec, expected_btype) in enumerate(starter_expected, start=1):
            uid = base_uid + idx
            comp = await CompanyService.create_company(session, uid, f"Comp {spec}_{base_uid}", alias)
            assert comp.specialization == spec, f"Expected spec {spec}, got {comp.specialization}"
            from sqlalchemy import select
            res = await session.execute(select(NatFactory).where(NatFactory.company_id == comp.id))
            fac = res.scalars().first()
            assert fac.building_type == expected_btype, f"Expected starter {expected_btype}, got {fac.building_type}"
            assert fac.current_recipe is None, "Idle starter factory must not pretend a cycle is running"
            starter_spec = get_building_spec(fac.building_type)
            assert starter_spec["recipe_id"] in RECIPES
            print(f"[{idx}/31 OK] {alias} -> {spec} -> {expected_btype} with canonical recipe {starter_spec['recipe_id']}")

    # 9: Build 5 different buildings
    print("\n--- [9/31] Build 5 Different Buildings ---")
    async with async_session_factory() as session:
        uid = base_uid + 100
        comp = await CompanyService.create_company(session, uid, f"MultiBuilder_{base_uid}", "metallurgist")
        comp.cash = 3000000.0
        comp.territory_tiles = 10
        comp.level = 60
        buildings_to_build = ["rolling_mill", "metal_structures_factory", "machine_factory", "auto_components_factory", "superalloy_factory"]
        for b_id in buildings_to_build:
            res = await BuildingService.build_factory(session, comp, b_id)
            assert res["success"] is True
            assert res["building_type"] == b_id
        builder_comp_id = comp.id
        print(f"[9/31 OK] Successfully built 5 distinct buildings. Remaining cash: {comp.cash:,.0f}")

    # 10: Cannot build locked building
    print("\n--- [10/31] Level Requirement Enforcement ---")
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, builder_comp_id)
        comp.level = 1
        try:
            await BuildingService.build_factory(session, comp, "superalloy_factory")
            assert False, "Should not build tier 4 building with level 1"
        except ValueError as err:
            assert "level" in str(err).lower()
            print(f"[10/31 OK] Correctly blocked under-leveled build: {err}")

    # 11: Cannot build without enough Cash
    print("\n--- [11/31] Cash Requirement Enforcement ---")
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, builder_comp_id)
        comp.level = 60
        comp.cash = 10.0
        try:
            await BuildingService.build_factory(session, comp, "rolling_mill")
            assert False, "Should not build without enough cash"
        except ValueError as err:
            assert "cash" in str(err).lower()
            print(f"[11/31 OK] Correctly blocked build without cash: {err}")

    # 12-14: Efficiency checks (10% foreign, max 12% licensed, 100% own)
    print("\n--- [12-14/31] Efficiency Checks (100% vs 10% vs max 12%) ---")
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, builder_comp_id)
        comp.cash = 500000.0
        comp.level = 10
        comp.territory_tiles = 15
        # Foreign build (chemist building by metallurgist company)
        res_foreign = await BuildingService.build_factory(session, comp, "chemical_plant")
        assert res_foreign["efficiency"] == 0.10
        print(f"[12/31 OK] Foreign factory efficiency: {res_foreign['efficiency'] * 100}% (0.10)")

        # Licensed foreign check
        comp.licensed_foreign_spec = "chemist"
        res_lic = await BuildingService.build_factory(session, comp, "fertilizer_plant")
        assert res_lic["efficiency"] <= 0.12 and res_lic["efficiency"] == 0.12
        print(f"[13/31 OK] Licensed foreign efficiency: {res_lic['efficiency'] * 100}% (0.12 ceiling)")

        # Own specialization build
        res_own = await BuildingService.build_factory(session, comp, "rolling_mill")
        own_factory_id = res_own["factory_id"]
        assert res_own["efficiency"] == 1.0
        print(f"[14/31 OK] Own specialization efficiency: {res_own['efficiency'] * 100}% (1.0)")

    # 15-19: Production cycle lifecycle (start, double-start, collect before ready, collect, second cycle)
    print("\n--- [15-19/31] Production Cycle Lifecycle ---")
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, comp.id)
        now = get_game_now()
        from sqlalchemy import select
        comp = await session.get(NatCompany, builder_comp_id)
        fac_res = await session.execute(select(NatFactory).where(NatFactory.id == own_factory_id))
        my_fac = fac_res.scalar_one()

        # Seed necessary inputs for rolling_mill: steel: 2.0, energy: 4.0
        for itm, qty in [("steel", 100.0), ("energy", 100.0)]:
            r = await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == comp.id,
                    NatInventory.item_id == itm
                )
            )
            inv = r.scalar_one_or_none()
            if inv:
                inv.quantity = qty
            else:
                session.add(NatInventory(company_id=comp.id, item_id=itm, quantity=qty))
        await session.flush()

        # 15: Start cycle
        start_res = await ProductionTickEngine.start_cycle(session, comp, my_fac, now=now)
        assert start_res["success"] is True
        print(f"[15/31 OK] Cycle started successfully. Duration: {start_res['duration_seconds']}s")

        # 16: Cannot start twice
        double_start = await ProductionTickEngine.start_cycle(session, comp, my_fac, now=now)
        assert double_start["success"] is False
        assert double_start["reason"] in ("cycle_in_progress", "cycle_ready_to_collect")
        print(f"[16/31 OK] Prevented double cycle start: {double_start['reason']}")

        # 17: Cannot collect before ready_at
        early_collect = await ProductionTickEngine.complete_cycle(session, comp, my_fac, now=now + timedelta(seconds=5))
        assert early_collect["success"] is False
        assert early_collect["reason"] == "cycle_in_progress"
        print(f"[17/31 OK] Prevented early collect. Remaining: {early_collect.get('remaining_seconds')}s")

        # 18: Can collect after ready_at
        ready_time = now + timedelta(seconds=start_res["duration_seconds"] + 5)
        collect_res = await ProductionTickEngine.complete_cycle(session, comp, my_fac, now=ready_time)
        assert collect_res["success"] is True
        assert "rolled_metal" in collect_res["outputs_produced"]
        print(f"[18/31 OK] Successfully collected output: {collect_res['outputs_produced']}")

        # 19: Second cycle can be started after first is collected
        second_start = await ProductionTickEngine.start_cycle(session, comp, my_fac, now=ready_time)
        assert second_start["success"] is True
        print("[19/31 OK] Second cycle started successfully after collection.")
        ready_time2 = ready_time + timedelta(seconds=second_start["duration_seconds"] + 5)
        await ProductionTickEngine.complete_cycle(session, comp, my_fac, now=ready_time2)

    # 20-21: Recipe mismatches
    print("\n--- [20-21/31] Recipe Factory and Specialization Mismatch ---")
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, builder_comp_id)
        my_fac = await session.get(NatFactory, own_factory_id)
        # Wrong recipe for factory
        wrong_recipe = await ProductionTickEngine.start_cycle(session, comp, my_fac, recipe_id="pump_oil_crude")
        assert wrong_recipe["success"] is False
        print(f"[20/31 OK] Wrong factory recipe rejected: {wrong_recipe.get('reason')}")

        # Wrong specialization recipe
        wrong_spec = await ProductionTickEngine.start_cycle(session, comp, my_fac, recipe_id="farm_grain")
        assert wrong_spec["success"] is False
        print(f"[21/31 OK] Specialization mismatch rejected: {wrong_spec.get('reason')}")

    # 22-26: Upgrades (workers, automation, technology, level bypass, double spend)
    print("\n--- [22-26/31] Upgrades & Economic Security ---")
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, builder_comp_id)
        my_fac = await session.get(NatFactory, own_factory_id)
        comp.cash = 100000.0
        init_workers = my_fac.workers
        up_w = await BuildingService.upgrade_factory(session, comp, my_fac.id, "workers")
        assert up_w["workers"] == init_workers + 10
        print(f"[22/31 OK] Upgraded workers to {up_w['workers']}")

        init_auto = my_fac.automation_level
        up_a = await BuildingService.upgrade_factory(session, comp, my_fac.id, "automation")
        assert up_a["automation_level"] == init_auto + 1
        print(f"[23/31 OK] Upgraded automation to {up_a['automation_level']}")

        init_tech = my_fac.technology_level
        up_t = await BuildingService.upgrade_factory(session, comp, my_fac.id, "technology")
        assert up_t["technology_level"] == init_tech + 1
        print(f"[24/31 OK] Upgraded technology to {up_t['technology_level']}")

        # 25: Cannot bypass level requirements
        comp.level = 1
        my_fac.level = 1
        try:
            await BuildingService.upgrade_factory(session, comp, my_fac.id, "level")
            assert False, "Factory level should not exceed company level"
        except ValueError as err:
            assert "level" in str(err).lower() or "уров" in str(err).lower()
            print(f"[25/31 OK] Level requirement enforcement in upgrades: {err}")

        # 26: Cannot spend money twice
        comp.cash = 0.0
        try:
            await BuildingService.upgrade_factory(session, comp, my_fac.id, "workers")
            assert False, "Should not upgrade without money"
        except ValueError as err:
            assert "cash" in str(err).lower()
            print(f"[26/31 OK] Prevented upgrade with zero balance: {err}")

    # 27-29: Concurrency protection simulation
    print("\n--- [27-29/31] Concurrency Protection Simulation ---")
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, builder_comp_id)
        my_fac = await session.get(NatFactory, own_factory_id)
        comp.cash = 60000.0  # Enough for exactly one rolling_mill at the expanded 52,000 cost.
        comp.level = 20
        comp.territory_tiles = 25

        # SQLite does not implement SELECT .. FOR UPDATE semantics. Verify the
        # invariant sequentially here; PostgreSQL row-locking is used in production.
        first_build = await BuildingService.build_factory(session, comp, "rolling_mill")
        assert first_build["success"] is True
        try:
            await BuildingService.build_factory(session, comp, "rolling_mill")
            assert False, "Second build must fail after the first consumes available cash"
        except ValueError as err:
            assert "cash" in str(err).lower()
        print("[27/31 OK] Double-build spend protected; production DB uses row locks for concurrent workers.")

        # Simulate concurrent production start
        my_fac.cycle_ready_at = None
        my_fac.current_recipe = None
        for itm, qty in [("steel", 50.0), ("energy", 50.0)]:
            r = await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == comp.id,
                    NatInventory.item_id == itm
                )
            )
            inv = r.scalar_one_or_none()
            if inv:
                inv.quantity = qty
            else:
                session.add(NatInventory(company_id=comp.id, item_id=itm, quantity=qty, reserved_quantity=0.0, avg_cost_basis=0.0))
        await session.flush()
        now = get_game_now()
        t_start1 = ProductionTickEngine.start_cycle(session, comp, my_fac, now=now)
        t_start2 = ProductionTickEngine.start_cycle(session, comp, my_fac, now=now)
        res_starts = await asyncio.gather(t_start1, t_start2)
        starts_ok = sum(1 for r in res_starts if r.get("success"))
        assert starts_ok == 1, f"Expected 1 start success, got {starts_ok}"
        print(f"[28/31 OK] Concurrent production start protected: exactly 1 cycle started.")

        # Simulate concurrent collect
        ready_time = now + timedelta(seconds=120)
        t_col1 = ProductionTickEngine.complete_cycle(session, comp, my_fac, now=ready_time)
        t_col2 = ProductionTickEngine.complete_cycle(session, comp, my_fac, now=ready_time)
        res_cols = await asyncio.gather(t_col1, t_col2)
        cols_ok = sum(1 for r in res_cols if r.get("success"))
        assert cols_ok == 1, f"Expected 1 collect success, got {cols_ok}"
        print(f"[29/31 OK] Concurrent collect protected: exactly 1 collected.")

    # 30: DAG validator detects cycles
    print("\n--- [30/31] DAG Validator Cycle Detection ---")
    from backend.natbirzha.services.recipes import validate_recipe_dag
    assert validate_recipe_dag() is True
    # Intentionally inject a cycle in a temporary copy to verify detector raises ValueError
    test_graph = dict(RECIPES)
    test_graph["cycle_bad"] = {"inputs": {"rolled_metal": 1.0}, "outputs": {"iron_ore": 1.0}}
    import copy
    orig_recipes = copy.deepcopy(RECIPES)
    try:
        RECIPES["cycle_bad"] = {"inputs": {"rolled_metal": 1.0}, "outputs": {"iron_ore": 1.0}}
        validate_recipe_dag()
        assert False, "DAG validator must detect cycle!"
    except ValueError as err:
        assert "cycle" in str(err).lower()
        print(f"[30/31 OK] DAG validator correctly caught synthetic cycle: {err}")
    finally:
        RECIPES.clear()
        RECIPES.update(orig_recipes)

    # 31: All 8 starter factories have valid recipes
    print("\n--- [31/31] Starter Factories Recipe Validity ---")
    for spec, b_id in STARTER_FACTORIES.items():
        spec_data = get_building_spec(b_id)
        assert spec_data is not None, f"Starter factory {b_id} missing from CANONICAL_BUILDINGS"
        recipe = RECIPES.get(spec_data["recipe_id"]) or RECIPES.get(b_id)
        assert recipe is not None, f"Starter factory {b_id} has no recipe registered"
        assert len(recipe["outputs"]) > 0, f"Recipe for {b_id} has no outputs"
    print("[31/31 OK] All 8 starter factories have valid, productive canonical recipes!")

    print("\n" + "=" * 64)
    print("🌟 ALL 31/31 ENTERPRISE EXPANSION TEST POINTS PASSED PERFECTLY! 🌟")
    print("=" * 64 + "\n")

if __name__ == "__main__":
    asyncio.run(run_all_expansion_tests())
