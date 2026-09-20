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
from backend.db.crud.rpg.forge_math import (
    RARITY_TIERS,
    FORGE_MAX_LEVEL,
    get_forge_upgrade_requirements,
    apply_forge_upgrade_to_item,
)
from backend.db.crud.rpg.inventory import (
    upgrade_item_forge,
    equip_item_for_character,
)
from backend.db.crud.rpg.character import get_or_create_rpg_character


def test_forge_items_suite():
    asyncio.run(run_forge_items_suite())


async def run_forge_items_suite():
    await init_db()
    print("\n=== [1/3] Testing Rarity Tiers & Forge Math (Volume V) ===")

    # 1. 7 Rarity Tiers Verification
    assert len(RARITY_TIERS) == 7, f"Expected 7 canonical rarity tiers, got {len(RARITY_TIERS)}"
    expected_tiers = ["common", "uncommon", "rare", "epic", "legendary", "mythic", "immortal"]
    for t in expected_tiers:
        assert t in RARITY_TIERS, f"Missing tier {t}"
    assert RARITY_TIERS["common"]["multiplier"] == 1.00
    assert RARITY_TIERS["uncommon"]["multiplier"] == 1.30
    assert RARITY_TIERS["rare"]["multiplier"] == 1.75
    assert RARITY_TIERS["epic"]["multiplier"] == 2.40
    assert RARITY_TIERS["legendary"]["multiplier"] == 3.40
    assert RARITY_TIERS["mythic"]["multiplier"] == 4.80
    assert RARITY_TIERS["immortal"]["multiplier"] == 6.80
    print(f"[OK] 7 Rarity Tiers strictly verified: {[t['name'] + ' (x' + str(t['multiplier']) + ')' for t in RARITY_TIERS.values()]}")

    # 2. Forge Requirements Table (Volume V, p. 5.3)
    # +1: 100%, 350 gold, 0 gems
    req1 = get_forge_upgrade_requirements(0)
    assert req1["target_level"] == 1
    assert req1["success_rate"] == 1.00
    assert req1["gold_cost"] == 350
    assert req1["gems_cost"] == 0

    # +4: 98%, 3200 gold, 2 gems
    req4 = get_forge_upgrade_requirements(3)
    assert req4["target_level"] == 4
    assert req4["success_rate"] == 0.98
    assert req4["gold_cost"] == 4 * 800
    assert req4["gems_cost"] == 2

    # +8: 90%, 16000 gold, 6 gems
    req8 = get_forge_upgrade_requirements(7)
    assert req8["target_level"] == 8
    assert req8["success_rate"] == 0.90
    assert req8["gold_cost"] == 8 * 2000
    assert req8["gems_cost"] == 6

    # +11: 75%, 60500 gold, 15 gems
    req11 = get_forge_upgrade_requirements(10)
    assert req11["target_level"] == 11
    assert req11["success_rate"] == 0.75
    assert req11["gold_cost"] == 11 * 5500
    assert req11["gems_cost"] == 15

    # +15: 60%, 225000 gold, 45 gems
    req15 = get_forge_upgrade_requirements(14)
    assert req15["target_level"] == 15
    assert req15["success_rate"] == 0.60
    assert req15["gold_cost"] == 15 * 15000
    assert req15["gems_cost"] == 45

    # +50: 50% success, level up to 100
    req50 = get_forge_upgrade_requirements(49)
    assert req50["target_level"] == 50
    assert req50["success_rate"] == 0.50
    assert req50["is_max"] is False

    # Max level check (+100)
    req_max = get_forge_upgrade_requirements(100)
    assert req_max["is_max"] is True
    assert req_max["success_rate"] == 0.0
    print("[OK] Forge Requirements & Probability Table (+1..+100) verified!")

    # 3. Stat Growth formula: Stat_final = Stat_base * calculate_forge_multiplier(level)
    sample_weapon = {
        "uid": "test_wpn_1",
        "name": "Клинок Даэдра",
        "type": "weapon",
        "slot": "weapon",
        "base_min": 20,
        "base_max": 40,
        "bonus": {"str": 10, "crit": 15},
    }
    upg1 = apply_forge_upgrade_to_item(dict(sample_weapon), 1)
    # At +1: 20 * 1.10 = 22, 40 * 1.10 = 44, str 10 * 1.10 = 11
    assert upg1["min_atk"] == 22
    assert upg1["max_atk"] == 44
    assert upg1["bonus"]["str"] == 11
    print(f"[OK] Stat Growth +1 verified: ATK {sample_weapon['base_min']}..{sample_weapon['base_max']} -> {upg1['min_atk']}..{upg1['max_atk']}, STR -> {upg1['bonus']['str']}")

    upg15 = apply_forge_upgrade_to_item(dict(sample_weapon), 15)
    # At +15: 20 * 2.50 = 50, 40 * 2.50 = 100
    assert upg15["min_atk"] == 50
    assert upg15["max_atk"] == 100
    print(f"[OK] Stat Growth +15 verified: ATK {sample_weapon['base_min']}..{sample_weapon['base_max']} -> {upg15['min_atk']}..{upg15['max_atk']} (+150% stats!)")

    print("\n=== [2/3] Testing Forge CRUD & Safety Guarantees ===")
    async for session in get_db_session():
        test_uid = 99112233
        char = await get_or_create_rpg_character(session, user_id=test_uid, preferred_class="pudge")
        char.gold = 500000
        char.gems = 200

        # Find or inject test weapon in inventory
        test_item = {
            "uid": "item_forge_test_01",
            "name": "Демонический Топор",
            "type": "weapon",
            "slot": "weapon",
            "rarity": "rare",
            "base_min": 30,
            "base_max": 50,
            "min_atk": 30,
            "max_atk": 50,
            "upgrade": 0,
            "bonus": {"str": 12, "lifesteal": 10},
        }
        char.inventory = [test_item]
        await session.commit()

        # Step A: Upgrade +1 (100% success)
        ok, msg, forged_item = await upgrade_item_forge(session, char, "item_forge_test_01")
        assert ok, f"Upgrade +1 failed: {msg}"
        assert forged_item["upgrade"] == 1
        assert forged_item["min_atk"] == int(round(30 * 1.10))
        print(f"[OK] Upgrade to +1 successful: {msg}")

        # Step B: Insufficient Gold check
        char.gold = 10
        await session.commit()
        ok_no_gold, msg_no_gold, _ = await upgrade_item_forge(session, char, "item_forge_test_01")
        assert not ok_no_gold, "Must reject forge with insufficient gold"
        assert "Не хватает золота" in msg_no_gold
        print(f"[OK] Insufficient gold properly rejected: {msg_no_gold}")

        # Step C: Insufficient Gems check (at +4 requires 2 gems)
        char.gold = 50000
        char.gems = 0
        test_item["upgrade"] = 3
        char.inventory = [test_item]
        await session.commit()
        ok_no_gems, msg_no_gems, _ = await upgrade_item_forge(session, char, "item_forge_test_01")
        assert not ok_no_gems, "Must reject forge with insufficient gems"
        assert "Не хватает кристаллов" in msg_no_gems
        print(f"[OK] Insufficient gems properly rejected: {msg_no_gems}")

        # Step D: Max level +100 cap enforcement
        test_item["upgrade"] = 100
        char.inventory = [test_item]
        await session.commit()
        ok_max, msg_max, _ = await upgrade_item_forge(session, char, "item_forge_test_01")
        assert not ok_max, "Must reject forge at max level 100"
        assert "максимального" in msg_max
        print(f"[OK] Maximum level +100 cap properly enforced: {msg_max}")
        break

    print("\n=== [3/3] Testing Forge HTTP Endpoints ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # GET /api/rpg/items/rarities
        r_rarities = await client.get("/api/rpg/items/rarities")
        assert r_rarities.status_code == 200
        rarities_data = r_rarities.json()
        assert len(rarities_data) == 7
        print(f"[OK] GET /api/rpg/items/rarities returned {len(rarities_data)} tiers.")

        # Prepare character with item for HTTP test
        async for session in get_db_session():
            char = await get_or_create_rpg_character(session, user_id=1)
            char.gold = 10000
            char.gems = 50
            http_item = {
                "uid": "http_forge_item_99",
                "name": "Священная Рапира",
                "type": "weapon",
                "slot": "weapon",
                "rarity": "mythic",
                "base_min": 100,
                "base_max": 150,
                "min_atk": 100,
                "max_atk": 150,
                "upgrade": 0,
                "bonus": {"atk": 50},
            }
            char.inventory = [http_item]
            await session.commit()
            break

        # GET /api/rpg/forge/info/{item_uid}
        r_info = await client.get("/api/rpg/forge/info/http_forge_item_99")
        assert r_info.status_code == 200, f"Forge info failed: {r_info.text}"
        info_resp = r_info.json()
        assert info_resp["item_uid"] == "http_forge_item_99"
        assert info_resp["requirements"]["target_level"] == 1
        assert info_resp["preview_item"]["min_atk"] == int(round(100 * 1.10))
        print(f"[OK] GET /api/rpg/forge/info verified: Target +1, Gold: {info_resp['requirements']['gold_cost']}, Preview ATK: {info_resp['preview_item']['min_atk']}")

        # POST /api/rpg/inventory/forge
        r_forge = await client.post("/api/rpg/inventory/forge", json={"item_uid": "http_forge_item_99"})
        assert r_forge.status_code == 200, f"Forge post failed: {r_forge.text}"
        forge_resp = r_forge.json()
        assert forge_resp["success"] is True
        assert forge_resp["item"]["upgrade"] == 1
        print(f"[OK] POST /api/rpg/inventory/forge succeeded! Message: {forge_resp['message']}")

    print("\n=== ALL FORGE & DOTA ARTIFACT TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    test_forge_items_suite()
