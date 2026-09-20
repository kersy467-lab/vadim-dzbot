import os
import sys
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_rpg.db"

from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.session import init_db
from backend.db.crud.rpg.progression_math import (
    calculate_xp_for_level,
    calculate_base_attribute_stats,
    get_unlocked_features,
    LEVEL_CAP,
    STAT_POINTS_PER_LEVEL,
    PROGRESSION_MILESTONES,
)


def test_heroes_and_progression():
    asyncio.run(run_heroes_progression_suite())


async def run_heroes_progression_suite():
    await init_db()
    print("\n=== [1/3] Testing Mathematical Formulas (Volume III) ===")

    # 1. Test XP formula
    xp_lvl_1 = calculate_xp_for_level(1)
    assert xp_lvl_1 == 150, f"Level 1 XP should be 150, got {xp_lvl_1}"
    xp_lvl_5 = calculate_xp_for_level(5)
    assert xp_lvl_5 > xp_lvl_1, "XP requirement must scale with level"
    print(f"[OK] XP formula verified: Lvl 1 -> {xp_lvl_1} XP, Lvl 5 -> {xp_lvl_5} XP, Cap -> {LEVEL_CAP}")

    # 2. Test Attribute scaling formulas
    str_stats = calculate_base_attribute_stats(strength=20, agility=10, intelligence=10, primary_attr="Сила")
    assert str_stats["hp"] == 150 + (20 * 24), f"STR HP mismatch: {str_stats['hp']}"
    assert str_stats["hp_regen"] == round(0.5 + (20 * 0.08), 2)
    assert str_stats["base_atk"] == round(20 * 1.8, 1)

    agi_stats = calculate_base_attribute_stats(strength=10, agility=25, intelligence=10, primary_attr="Ловкость")
    assert agi_stats["armor"] == int(25 * 0.18)
    assert agi_stats["crit_chance"] == round(5.0 + (25 * 0.12), 2)
    assert agi_stats["base_atk"] == round(25 * 1.8, 1)

    int_stats = calculate_base_attribute_stats(strength=10, agility=10, intelligence=30, primary_attr="Интеллект")
    assert int_stats["mp"] == 100 + (30 * 16)
    assert int_stats["mp_regen"] == round(1.0 + (30 * 0.10), 2)
    assert int_stats["spell_power"] == round(1.0 + (30 * 0.015), 3)
    assert int_stats["base_atk"] == round(30 * 1.8, 1)
    print("[OK] Base attribute formulas strictly match GDD Volume III!")

    # 3. Test Feature unlocks by level
    lvl_1_features = get_unlocked_features(1)
    assert lvl_1_features["skill_1"] is True
    assert lvl_1_features["pets"] is False
    assert lvl_1_features["ultimate"] is False

    lvl_5_features = get_unlocked_features(5)
    assert lvl_5_features["pets"] is True
    assert lvl_5_features["skill_2"] is True
    assert lvl_5_features["ultimate"] is False

    lvl_20_features = get_unlocked_features(20)
    assert lvl_20_features["ultimate"] is True
    assert lvl_20_features["talent_15"] is True

    lvl_50_features = get_unlocked_features(50)
    assert lvl_50_features["nightmare_raids"] is True
    assert lvl_50_features["rebirth_rank_4"] is True
    print("[OK] Level milestone unlock matrix strictly verified!")

    print("\n=== [2/3] Testing Detailed Heroes API (/heroes/detailed, /heroes/{id}) ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Check detailed heroes endpoint
        r = await client.get("/api/rpg/heroes/detailed")
        assert r.status_code == 200, f"Heroes detailed failed: {r.text}"
        heroes = r.json()
        assert len(heroes) == 8, f"Expected 8 Dota 2 heroes, got {len(heroes)}"

        hero_ids = {h["id"] for h in heroes}
        expected_ids = {"pudge", "juggernaut", "phantom_assassin", "shadow_fiend", "invoker", "wraith_king", "anti_mage", "leshrac"}
        assert hero_ids == expected_ids, f"Mismatch in hero IDs: {hero_ids}"

        for h in heroes:
            assert len(h.get("skills", [])) == 4, f"Hero {h['id']} must have 4 skills (Q, E, R, F), got {len(h.get('skills', []))}"
            assert set(h.get("talents", {}).keys()) == {"10", "15", "20", "25"}, f"Hero {h['id']} missing talent tiers: {h.get('talents')}"
            print(f"  [OK] Hero '{h['id']}': {len(h['skills'])} skills, {len(h['talents'])} talent tiers.")

        # Test single hero endpoint
        r_pudge = await client.get("/api/rpg/heroes/pudge")
        assert r_pudge.status_code == 200
        p_data = r_pudge.json()
        assert p_data["id"] == "pudge"
        assert p_data["attr"] == "Сила"

        # Test 404 for unknown hero
        r_unknown = await client.get("/api/rpg/heroes/unknown_hero_xyz")
        assert r_unknown.status_code == 404

        print("\n=== [3/3] Testing Progression Table & Milestones API ===")
        # Test progression table
        r_table = await client.get("/api/rpg/progression/table")
        assert r_table.status_code == 200
        t_data = r_table.json()
        assert t_data["level_cap"] == LEVEL_CAP
        assert t_data["stat_points_per_level"] == STAT_POINTS_PER_LEVEL
        assert len(t_data["table"]) == LEVEL_CAP
        print(f"[OK] Progression table endpoint verified: {len(t_data['table'])} levels returned.")

        # Test milestones
        r_milestones = await client.get("/api/rpg/progression/milestones")
        assert r_milestones.status_code == 200
        m_data = r_milestones.json()
        assert "5" in m_data or 5 in m_data
        assert "20" in m_data or 20 in m_data
        print("[OK] Progression milestones endpoint verified.")

        # Test my unlocked features
        r_unlocked = await client.get("/api/rpg/progression/unlocked")
        assert r_unlocked.status_code == 200
        u_data = r_unlocked.json()
        assert "unlocked_features" in u_data
        assert "level" in u_data
        print(f"[OK] Character progression status verified for level {u_data['level']}.")

    print("\n=======================================================")
    print(">>> ALL HEROES & PROGRESSION TESTS PASSED SUCCESSFULLY! <<<")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(run_heroes_progression_suite())
