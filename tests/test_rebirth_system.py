import os
import sys
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_rpg.db"

from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.session import init_db, get_db_session
from backend.db.crud.rpg.rebirth import (
    calculate_rebirth_multiplier,
    get_rebirth_rank_info,
    perform_ascension,
    upgrade_constellation,
    CONSTELLATIONS_CATALOG,
    REBIRTH_RANKS_CONFIG,
    MAX_REBIRTH_RANK,
)
from backend.db.crud.rpg.character import get_or_create_rpg_character, serialize_character_profile
from backend.db.crud.rpg.character_stats import calculate_character_effective_stats


def test_rebirth_suite():
    asyncio.run(run_rebirth_suite())


async def run_rebirth_suite():
    await init_db()
    print("\n=== [1/3] Testing Rebirth & Ascension Math (Volume IV) ===")

    # 1. Multiplier Formula: M(R) = 1 + (R * 0.35) + (R^1.3 * 0.08)
    m0 = calculate_rebirth_multiplier(0)
    assert m0 == 1.0, f"Rank 0 multiplier must be 1.0, got {m0}"

    m1 = calculate_rebirth_multiplier(1)
    # 1 + 0.35 + 0.08 = 1.43
    assert abs(m1 - 1.43) < 0.001, f"Rank 1 multiplier must be 1.43, got {m1}"

    m2 = calculate_rebirth_multiplier(2)
    # 1 + 0.70 + (2^1.3 * 0.08) = 1.897
    assert abs(m2 - 1.897) < 0.01, f"Rank 2 multiplier must be ~1.897, got {m2}"

    m10 = calculate_rebirth_multiplier(10)
    assert m10 > m2, f"Rank 10 multiplier must exceed Rank 2, got {m10}"

    m40 = calculate_rebirth_multiplier(40)
    assert m40 > m10, f"Rank 40 multiplier must exceed Rank 10, got {m40}"
    print(f"[OK] Rebirth Multipliers: Rank 0 -> x{m0}, Rank 1 -> x{m1} (+43%), Rank 2 -> x{m2} (+89.7%), Rank 10 -> x{m10}, Rank 40 -> x{m40}")

    assert len(REBIRTH_RANKS_CONFIG) == 41, f"Expected 41 ranks (0 to 40), got {len(REBIRTH_RANKS_CONFIG)}"
    assert MAX_REBIRTH_RANK == 40
    r40_info = get_rebirth_rank_info(40)
    assert r40_info["rank"] == 40
    assert r40_info["next_rank"] is None
    print(f"[OK] Rebirth Rank 40 verified: «{r40_info['title']}», Multiplier: x{r40_info['multiplier']}")

    # 2. Check Configurations
    assert len(CONSTELLATIONS_CATALOG) == 6, f"Expected 6 Astral Constellations, got {len(CONSTELLATIONS_CATALOG)}"
    for cid, ccfg in CONSTELLATIONS_CATALOG.items():
        assert ccfg["max_level"] in (10, 30)
        assert "desc" in ccfg
    print(f"[OK] 6 Astral Constellations verified in catalog: {list(CONSTELLATIONS_CATALOG.keys())}")

    print("\n=== [2/3] Testing In-Engine Ascension & Constellations CRUD ===")
    async for session in get_db_session():
        # Character for testing
        test_uid = 99881122
        char = await get_or_create_rpg_character(session, user_id=test_uid, preferred_class="juggernaut")
        char.rebirths = 0
        char.level = 10
        char.gold = 5000
        char.gems = 150
        char.talents = {}
        await session.commit()

        # Step A: Attempt ascension at level 10 (should fail, needs lvl 30)
        ok, msg, _ = await perform_ascension(session, char)
        assert not ok, "Ascension at level 10 should be rejected!"
        assert "30" in msg, f"Error message should mention required level 30: {msg}"
        print(f"[OK] Premature ascension blocked: {msg}")

        # Step B: Level up to 30 and ascend
        char.level = 30
        char.stat_points = 50
        await session.commit()

        ok, msg, details = await perform_ascension(session, char)
        assert ok, f"Ascension failed: {msg}"
        assert char.rebirths == 1
        assert char.level == 1
        assert char.stat_points == 0
        assert char.gold == 5000, "Gold must be preserved across rebirth!"
        assert char.gems == 150, "Gems must be preserved across rebirth!"
        assert details["essence_awarded"] == 3
        assert char.talents.get("rebirth_essence") == 3
        print(f"[OK] Ascension to Rank 1 successful: {msg}")

        # Step C: Upgrade Constellation Vitality
        ok_up, msg_up, up_res = await upgrade_constellation(session, char, "constellation_vitality")
        assert ok_up, f"Constellation upgrade failed: {msg_up}"
        assert up_res["new_level"] == 1
        assert up_res["remaining_essence"] == 2
        print(f"[OK] Constellation Vitality upgraded to Lvl 1: {msg_up}")

        # Step D: Verify stats reflect rebirth multiplier and constellation bonuses
        stats = calculate_character_effective_stats(char)
        assert stats["rebirth_multiplier"] == 1.43
        assert stats["constellations_bonuses"]["vitality_hp"] == 150
        assert stats["constellations_bonuses"]["vitality_armor"] == 5
        print(f"[OK] Effective stats reflect Rebirth x1.43 and Vitality bonus (+150 HP, +5 DEF)!")

        # Step E: Exhaust essence and verify rejection
        await upgrade_constellation(session, char, "constellation_vitality")
        await upgrade_constellation(session, char, "constellation_vitality")
        assert char.talents["rebirth_essence"] == 0
        ok_fail, msg_fail, _ = await upgrade_constellation(session, char, "constellation_vitality")
        assert not ok_fail, "Constellation upgrade without essence must fail"
        print(f"[OK] Insufficient essence correctly rejected: {msg_fail}")

        profile = serialize_character_profile(char, user_name="Тестовый Самурай")
        assert profile["rebirths"] == 1
        assert profile["rebirth_info"]["rank"] == 1
        assert profile["rebirth_info"]["multiplier"] == 1.43
        assert profile["rebirth_info"]["constellations"]["constellation_vitality"] == 3
        print("[OK] Profile serialization includes complete rebirth_info payload!")
        break

    print("\n=== [3/3] Testing Rebirth HTTP API Endpoints ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # GET /api/rpg/rebirth_system/info
        r_info = await client.get("/api/rpg/rebirth_system/info")
        assert r_info.status_code == 200, f"Rebirth info endpoint failed: {r_info.text}"
        info_data = r_info.json()
        assert "current_rank" in info_data
        assert "multiplier" in info_data
        assert "can_ascend" in info_data
        assert info_data.get("max_rank") == 40
        print(f"[OK] GET /api/rpg/rebirth_system/info response: Rank {info_data['current_rank']} ({info_data['title']}), Multiplier: x{info_data['multiplier']}, Max Rank: {info_data.get('max_rank')}")

        # GET /api/rpg/rebirth_system/constellations
        r_const = await client.get("/api/rpg/rebirth_system/constellations")
        assert r_const.status_code == 200, f"Constellations catalog failed: {r_const.text}"
        const_data = r_const.json()
        assert "constellations" in const_data
        assert len(const_data["constellations"]) == 6
        print(f"[OK] GET /api/rpg/rebirth_system/constellations returned {len(const_data['constellations'])} nodes.")

        # POST /api/rpg/rebirth_system/constellations/upgrade with invalid id
        r_bad = await client.post("/api/rpg/rebirth_system/constellations/upgrade", json={"constellation_id": "nonexistent"})
        assert r_bad.status_code == 400
        print("[OK] Invalid constellation ID properly returns 400 Bad Request.")

    print("\n=== ALL REBIRTH & ASCENSION TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    test_rebirth_suite()
