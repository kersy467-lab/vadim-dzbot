import os
import sys
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_rpg.db"

from backend.db.session import init_db, get_db_session
from backend.db.models import User, RPGCharacter
from backend.db.crud.rpg.character import get_or_create_rpg_character, serialize_character_profile
from backend.db.crud.rpg.talent_tree import (
    get_hero_available_talent_points,
    get_hero_spent_talent_points,
    get_hero_tree,
)
from backend.api.routers.heroes_dota import select_hero_class_endpoint


async def run_tests():
    print("=== [1/2] Testing Talent Persistence & Per-Hero Points ===")
    await init_db()

    async for session in get_db_session():
        # Create test character at level 40
        char = await get_or_create_rpg_character(session, user_id=99991)
        char.level = 40
        char.hero_class = "pudge"
        # Equip custom sword and armor
        char.equipment = {
            "slot_1": {"uid": "epic_blade_1", "name": "Клинок Бессмертия", "slot": "slot_1", "min_atk": 100, "max_atk": 150},
            "slot_2": {"uid": "epic_armor_1", "name": "Броня Титана", "slot": "slot_2", "defense": 80}
        }
        char.inventory = []
        char.talents = {"tree": {}}
        await session.commit()

        # Check total earned points: 40 // 2 = 20 points
        pts_pudge = get_hero_available_talent_points(char, "pudge")
        assert pts_pudge == 20, f"Expected 20 points, got {pts_pudge}"

        # Buy 2 talents on Pudge: atk_1 (cost 1), atk_2 (cost 1) -> 2 points spent
        char.talents = {"tree": {"pudge": {"atk_1": 1, "atk_2": 1}}}
        pts_pudge_after = get_hero_available_talent_points(char, "pudge")
        assert pts_pudge_after == 18, f"Expected 18 points for Pudge, got {pts_pudge_after}"

        # Check Leshrac points (should be full 20 points!)
        pts_leshrac = get_hero_available_talent_points(char, "leshrac")
        assert pts_leshrac == 20, f"Expected 20 points for Leshrac, got {pts_leshrac}"

        # Buy 1 talent on Leshrac: util_1 (cost 1) -> 1 point spent
        char.talents["tree"]["leshrac"] = {"util_1": 1}
        pts_leshrac_after = get_hero_available_talent_points(char, "leshrac")
        assert pts_leshrac_after == 19, f"Expected 19 points for Leshrac, got {pts_leshrac_after}"

        # Pudge should STILL have 18 points!
        assert get_hero_available_talent_points(char, "pudge") == 18

        print("[OK] Per-hero talent calculation strictly verified!")

        print("=== [2/2] Testing Equipment Preservation on Hero Switch ===")
        # Switch to Leshrac via select_hero_class_endpoint
        user_mock = await session.get(User, char.user_id)
        res = await select_hero_class_endpoint(
            payload={"hero_class": "leshrac"},
            user=user_mock,
            session=session
        )
        await session.refresh(char)

        assert char.hero_class == "leshrac"
        # Equipment must NOT be stripped or replaced with starter gear!
        assert char.equipment.get("slot_1", {}).get("uid") == "epic_blade_1", f"Equipment slot 1 was wiped! {char.equipment}"
        assert char.equipment.get("slot_2", {}).get("uid") == "epic_armor_1", f"Equipment slot 2 was wiped! {char.equipment}"
        assert len(char.inventory) == 0, f"Inventory received stripped items! {char.inventory}"

        # Check serialized profile talent points
        assert res["talent_points"] == 19, f"Expected 19 talent points in profile for Leshrac, got {res['talent_points']}"

        # Switch back to Pudge
        res_pudge = await select_hero_class_endpoint(
            payload={"hero_class": "pudge"},
            user=user_mock,
            session=session
        )
        await session.refresh(char)

        assert char.hero_class == "pudge"
        assert char.equipment.get("slot_1", {}).get("uid") == "epic_blade_1"
        assert res_pudge["talent_points"] == 18, f"Expected 18 talent points for Pudge, got {res_pudge['talent_points']}"
        assert char.talents["tree"]["pudge"]["atk_1"] == 1
        assert char.talents["tree"]["pudge"]["atk_2"] == 1
        assert char.talents["tree"]["leshrac"]["util_1"] == 1

        print("[OK] Equipment and talents completely preserved across hero switches!")

        print("=== [3/3] Testing 4th Flask Branch in Talent Tree ===")
        pudge_tree = get_hero_tree("pudge")
        assert "flask_1" in pudge_tree, "flask_1 not found in hero tree!"
        assert "flask_5" in pudge_tree, "flask_5 not found in hero tree!"
        assert pudge_tree["flask_1"]["branch"] == "flask"
        assert pudge_tree["flask_5"]["effect"].get("perk") == "perk_divine_flask"

        # Buy flask_1 and flask_2 on Pudge
        char.talents["tree"]["pudge"]["flask_1"] = 1
        char.talents["tree"]["pudge"]["flask_2"] = 1
        from backend.db.crud.rpg.character_stats import calculate_character_effective_stats
        stats = calculate_character_effective_stats(char)
        assert stats.get("flask_heal_flat") == 350 + 800, f"Expected 1150 flat heal, got {stats.get('flask_heal_flat')}"
        assert round(stats.get("flask_heal_pct", 0), 2) == 0.15, f"Expected 0.15 pct heal, got {stats.get('flask_heal_pct')}"
        assert stats.get("flask_mana") == 60, f"Expected 60 flask mana, got {stats.get('flask_mana')}"

        print("=== [4/4] Testing Level-Only Talent Unlocks (No Floor Fallback) ===")
        from backend.db.crud.rpg.talent_tree_helpers import is_node_available
        char.level = 1
        char.dungeon_floor = 50  # Even on floor 50!
        purchased = {"atk_1": 1}
        node_t2 = pudge_tree["atk_2"]  # unlock_level = 10

        # With level 1, tier 2 must NOT be available even on floor 50
        assert not is_node_available(node_t2, char.level, purchased), "Tier 2 node should NOT be available at level 1 even on floor 50!"

        # With level 10, tier 2 MUST be available
        char.level = 10
        assert is_node_available(node_t2, char.level, purchased), "Tier 2 node should be available at level 10!"

        print("[OK] Talent unlock is strictly gated by level only, ignoring floor!")
        print("\n=== ALL HERO TALENT, FLASK & EQUIPMENT TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    asyncio.run(run_tests())
