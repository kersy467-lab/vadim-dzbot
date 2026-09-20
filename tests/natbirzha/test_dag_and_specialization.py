import os
import sys
import pytest
import asyncio
from datetime import timedelta

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
from backend.natbirzha.services.recipes import RECIPES, validate_recipe_dag
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.company_service import CompanyService


async def test_dag_and_specialization():
    print("\n" + "=" * 64)
    print("🔬 TESTING RECIPE DAG & SPECIALIZATION EFFICIENCY CONSTRAINTS")
    print("=" * 64)

    # 1. Mathematical DAG cycle validation
    print("\n--- [1/3] Mathematical Directed Acyclic Graph (DAG) Integrity ---")
    is_dag_valid = validate_recipe_dag()
    assert is_dag_valid is True, "DAG validation failed!"
    assert len(RECIPES) >= 16, f"Expected at least 16 recipes, got {len(RECIPES)}"
    print(f"[OK] Recipe DAG is strictly acyclic across {len(RECIPES)} recipes. Zero loops.")

    await init_db()

    # 2. Strict Specialization Efficiency Ceiling (100% vs 10% vs max 12%)
    print("\n--- [2/3] Specialization Efficiency Limits (1.0 vs 0.10 vs 0.12) ---")
    async with async_session_factory() as session:
        now = get_game_now()
        company = NatCompany(
            user_id=777001,
            name="АгроХолдинг Тест",
            specialization="agrarian",
            level=1,
            xp=0,
            cash=100000.0,
            territory_tiles=4,
            created_at=now,
            updated_at=now
        )

        # Factory in OWN specialization (farm -> agrarian)
        own_factory = NatFactory(
            company_id=1,
            building_type="farm",
            specialization="agrarian",
            level=1,
            is_active=True,
            created_at=now
        )
        eff_own = ProductionTickEngine.get_effective_efficiency(company, own_factory)
        assert eff_own == 1.0, f"Own specialization must have 100% efficiency (1.0), got {eff_own}"
        print(f"[OK] Own specialization efficiency: {eff_own * 100}% (1.0).")

        # Factory in FOREIGN specialization (smelter -> metallurgist)
        foreign_factory = NatFactory(
            company_id=1,
            building_type="smelter",
            specialization="metallurgist",
            level=1,
            is_active=True,
            created_at=now
        )
        eff_foreign = ProductionTickEngine.get_effective_efficiency(company, foreign_factory)
        assert eff_foreign == 0.10, f"Foreign unlicensed efficiency must be 10% (0.10), got {eff_foreign}"
        print(f"[OK] Foreign unlicensed specialization efficiency: {eff_foreign * 100}% (0.10).")

        # Factory with licensed foreign specialization (licensed metallurgist)
        company.licensed_foreign_spec = "metallurgist"
        eff_licensed = ProductionTickEngine.get_effective_efficiency(company, foreign_factory)
        assert eff_licensed == 0.12, f"Foreign licensed efficiency must be strictly 12% (0.12), got {eff_licensed}"
        assert eff_licensed <= 0.12, "Licensed foreign efficiency must NEVER exceed 12%!"
        print(f"[OK] Foreign licensed specialization efficiency: {eff_licensed * 100}% (0.12 ceiling).")

    # 3. Specialization Respec Rules (25% fee, 7-day cooldown)
    print("\n--- [3/3] Specialization Respec & 7-Day Cooldown ---")
    import time
    async with async_session_factory() as session:
        user_respec_id = int(time.time()) % 1000000 + 700000
        comp_respec = await CompanyService.create_company(
            session, user_respec_id, f"Корпорация Респек {user_respec_id}", "oilman"
        )
        initial_cash = comp_respec.cash
        assert comp_respec.specialization == "oilman"

        # Execute valid respec
        respec_result = await CompanyService.change_specialization(session, comp_respec, "power_engineer")
        assert respec_result["success"] is True
        assert respec_result["new_specialization"] == "power_engineer"
        assert comp_respec.specialization == "power_engineer"
        assert comp_respec.cash < initial_cash, "25% NAV fee must be deducted"
        print(f"[OK] Respec successful to {comp_respec.specialization}. Fee paid: {respec_result['fee_paid']} cash.")

        # Attempt immediate second respec -> must raise cooldown error
        try:
            await CompanyService.change_specialization(session, comp_respec, "agrarian")
            assert False, "Immediate respec should have failed cooldown!"
        except ValueError as err:
            assert "cooldown" in str(err).lower()
            print(f"[OK] 7-Day cooldown properly rejected second respec: {err}")

    print("\n" + "=" * 64)
    print("🎉 ALL DAG & SPECIALIZATION CONSTRAINTS PASSED PERFECTLY!")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    asyncio.run(test_dag_and_specialization())
