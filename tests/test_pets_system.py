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
from backend.db.crud.rpg.pets_config import (
    PETS_CATALOG,
    PET_HATCH_RATES,
    MAX_PET_STARS,
    MERGE_COST_GEMS,
    HATCH_COST_GEMS,
)
from backend.db.crud.rpg.character import get_or_create_rpg_character
from backend.db.crud.rpg.character_stats import calculate_character_effective_stats


def test_pets_suite():
    asyncio.run(run_pets_suite())


async def run_pets_suite():
    await init_db()
    print("\n=== [1/3] Testing Pets Catalog & Math (Volume VIII) ===")

    # 1. 6 Pets in Catalog
    assert len(PETS_CATALOG) == 6, f"Expected 6 pets, got {len(PETS_CATALOG)}"
    expected_ids = {"slime", "fairy", "wolf", "dragon", "donkey", "phoenix"}
    assert set(PETS_CATALOG.keys()) == expected_ids, f"Pet catalog mismatch: {set(PETS_CATALOG.keys())}"

    for pid, pcfg in PETS_CATALOG.items():
        assert pcfg["stars_scaling"] == 0.08, f"Pet {pid} stars_scaling should be 0.08"
        assert "skill_name" in pcfg
        assert "skill_desc" in pcfg
        assert "cooldown_base" in pcfg
        print(f"  [OK] Pet '{pcfg['name']}' ({pcfg['rarity']}): Skill «{pcfg['skill_name']}» - {pcfg['skill_desc']}")

    # 2. Hatch Rates Total
    total_rates = sum(PET_HATCH_RATES.values())
    assert abs(total_rates - 100.0) < 0.01, f"Hatch rates must sum to 100%, got {total_rates}"
    assert PET_HATCH_RATES["mythic"] == 0.85
    assert PET_HATCH_RATES["immortal"] == 0.15
    print(f"[OK] Hatch rates sum to 100.0%: {PET_HATCH_RATES}")

    print("\n=== [2/3] Testing Pets In-Engine Stats Scaling ===")
    async for session in get_db_session():
        test_uid = 99223344
        char = await get_or_create_rpg_character(session, user_id=test_uid, preferred_class="pudge")
        char.rebirths = 0
        char.talents = {}
        char.pets = [
            {"uid": "pet_phoenix_1", "type": "phoenix", "stars": 1, "is_equipped": True}
        ]
        await session.commit()

        stats_1star = calculate_character_effective_stats(char)
        # Phoenix 1 star: base_hp_mult 1.35, base_dmg_mult 1.45
        # Let's unequip and check baseline
        char.pets[0]["is_equipped"] = False
        await session.commit()
        stats_no_pet = calculate_character_effective_stats(char)

        assert stats_1star["hp_max"] > stats_no_pet["hp_max"], "Equipped pet must boost HP"
        assert stats_1star["max_atk"] > stats_no_pet["max_atk"], "Equipped pet must boost ATK"
        print(f"[OK] Pet Phoenix 1★ boost verified: HP {stats_no_pet['hp_max']} -> {stats_1star['hp_max']}, ATK {stats_no_pet['max_atk']} -> {stats_1star['max_atk']}")

        # Test Star Scaling (3 stars = +16% extra boost)
        char.pets[0]["is_equipped"] = True
        char.pets[0]["stars"] = 3
        await session.commit()
        stats_3star = calculate_character_effective_stats(char)
        assert stats_3star["hp_max"] > stats_1star["hp_max"]
        assert stats_3star["max_atk"] > stats_1star["max_atk"]
        print(f"[OK] Pet Phoenix 3★ (+16% extra) verified: HP {stats_1star['hp_max']} -> {stats_3star['hp_max']}")
        break

    print("\n=== [3/3] Testing Pets HTTP Endpoints (Catalog, Hatch, Equip, 3-to-1 Merge) ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # GET /api/rpg/pets/catalog
        r_cat = await client.get("/api/rpg/pets/catalog")
        assert r_cat.status_code == 200, f"Catalog failed: {r_cat.text}"
        cat_data = r_cat.json()
        assert len(cat_data["pets"]) == 6
        assert cat_data["max_stars"] == 5
        assert cat_data["hatch_cost_gems"] == 50
        assert cat_data["merge_cost_gems"] == 10
        print(f"[OK] GET /api/rpg/pets/catalog returned {len(cat_data['pets'])} pets and configs.")

        # Prepare character with gems for hatching and merge
        async for session in get_db_session():
            char = await get_or_create_rpg_character(session, user_id=1)
            char.gems = 200
            char.pets = []
            await session.commit()
            break

        # POST /api/rpg/pets/hatch
        r_hatch = await client.post("/api/rpg/pets/hatch", json={})
        assert r_hatch.status_code == 200, f"Hatch failed: {r_hatch.text}"
        hatch_data = r_hatch.json()
        assert hatch_data["success"] is True
        hatched_pet = hatch_data["pet"]
        assert hatched_pet["stars"] == 1
        assert hatched_pet["is_equipped"] is False
        print(f"[OK] POST /api/rpg/pets/hatch successfully hatched: {hatch_data['pet_cfg']['name']} ({hatch_data['pet_cfg']['rarity']})")

        # POST /api/rpg/pets/equip
        r_equip = await client.post("/api/rpg/pets/equip", json={"pet_uid": hatched_pet["uid"]})
        assert r_equip.status_code == 200
        equip_prof = r_equip.json()["profile"]
        eq_pets = [p for p in equip_prof["pets"] if p["uid"] == hatched_pet["uid"]]
        assert eq_pets[0]["is_equipped"] is True
        print(f"[OK] POST /api/rpg/pets/equip equipped pet successfully!")

        # Inject 3 identical slimes for 3-to-1 merge test
        async for session in get_db_session():
            char = await get_or_create_rpg_character(session, user_id=1)
            char.gems = 50
            char.pets = [
                {"uid": "slime_a", "type": "slime", "stars": 1, "is_equipped": True},
                {"uid": "slime_b", "type": "slime", "stars": 1, "is_equipped": False},
                {"uid": "slime_c", "type": "slime", "stars": 1, "is_equipped": False},
            ]
            await session.commit()
            break

        # Test Merge 3-to-1
        r_up = await client.post("/api/rpg/pets/upgrade", json={"pet_uid": "slime_a"})
        assert r_up.status_code == 200, f"Upgrade failed: {r_up.text}"
        up_data = r_up.json()
        assert up_data["success"] is True
        assert up_data["stars"] == 2
        # Check resulting pets in profile: should be 1 pet of star 2
        res_pets = up_data["profile"]["pets"]
        assert len(res_pets) == 1
        assert res_pets[0]["uid"] == "slime_a"
        assert res_pets[0]["stars"] == 2
        # Check gems deducted (50 - 10 = 40)
        assert up_data["profile"]["gems"] == 40
        print(f"[OK] POST /api/rpg/pets/upgrade 3-to-1 Merge succeeded: {up_data['message']}")

        # Test Insufficient Pets rejection
        r_fail = await client.post("/api/rpg/pets/upgrade", json={"pet_uid": "slime_a"})
        assert r_fail.status_code == 400
        print("[OK] Attempt to merge with fewer than 3 identical pets properly rejected.")

        # Test Max Stars 5★ rejection
        async for session in get_db_session():
            char = await get_or_create_rpg_character(session, user_id=1)
            char.gems = 100
            char.pets = [
                {"uid": "slime_max_1", "type": "slime", "stars": 5, "is_equipped": True},
                {"uid": "slime_max_2", "type": "slime", "stars": 5, "is_equipped": False},
                {"uid": "slime_max_3", "type": "slime", "stars": 5, "is_equipped": False},
            ]
            await session.commit()
            break

        r_max = await client.post("/api/rpg/pets/upgrade", json={"pet_uid": "slime_max_1"})
        assert r_max.status_code == 400
        assert "5★" in r_max.json()["detail"] or "максимального" in r_max.json()["detail"]
        print("[OK] Merge beyond max 5★ properly rejected.")

    print("\n=== ALL PETS & SYNTHESIS TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    test_pets_suite()
