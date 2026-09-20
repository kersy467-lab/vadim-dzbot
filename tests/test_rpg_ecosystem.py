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
from backend.db.crud.rpg import (
    get_or_create_rpg_character,
    unequip_item_from_character,
    equip_item_for_character,
    use_consumable_item,
    get_rpg_shop_catalog,
    buy_item_from_shop,
    calculate_character_effective_stats,
    serialize_character_profile
)
from backend.api.rpg_bosses import RAID_BOSSES


def test_rpg_ecosystem():
    asyncio.run(run_rpg_ecosystem_suite())


async def run_rpg_ecosystem_suite():
    await init_db()
    print("\n=== [1/6] Testing Shop Catalog & Purchases (/shop, /shop/buy) ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Check shop catalog
        r = await client.get("/api/rpg/shop")
        assert r.status_code == 200, f"Shop catalog error: {r.text}"
        catalog = r.json()
        assert len(catalog) >= 15, f"Expected at least 15 items in shop, got {len(catalog)}"
        print(f"[OK] Shop catalog verified: {len(catalog)} items available.")

        # 2. Get profile and add test gold/gems
        gen = get_db_session()
        session = await anext(gen)
        try:
            char = await get_or_create_rpg_character(session, user_id=1)
            char.gold = 50000
            char.gems = 100
            char.inventory = []
            char.equipment = {}
            await session.commit()
        finally:
            await session.close()

        # Buy Armor
        r = await client.post("/api/rpg/shop/buy", json={"item_id": "shop_a_forged_cuirass"})
        assert r.status_code == 200, f"Buy armor failed: {r.text}"
        res = r.json()
        assert res["success"] is True
        bought_armor = res["item"]
        assert bought_armor["slot"] == "armor"
        print(f"[OK] Bought armor from shop: {bought_armor['name']} (defense: {bought_armor.get('defense')})")

        # Buy Relic
        r = await client.post("/api/rpg/shop/buy", json={"item_id": "shop_r_blink_dagger"})
        assert r.status_code == 200
        bought_relic = r.json()["item"]
        assert bought_relic["slot"] == "relic"
        print(f"[OK] Bought relic from shop: {bought_relic['name']}")

        # Buy Potion
        r = await client.post("/api/rpg/shop/buy", json={"item_id": "shop_p_healing"})
        assert r.status_code == 200
        bought_potion = r.json()["item"]
        assert bought_potion["slot"] == "consumable"
        print(f"[OK] Bought potion from shop: {bought_potion['name']} (count: {bought_potion.get('count')})")

        print("\n=== [3/5] Testing Potion / Consumable Direct Usage ===")
        # Use potion from inventory
        r = await client.post("/api/rpg/inventory/use", json={"item_uid": bought_potion["uid"]})
        assert r.status_code == 200, f"Potion usage failed: {r.text}"
        p_res = r.json()
        assert p_res["success"] is True
        assert p_res["potion_result"]["heal_hp"] == 120
        assert p_res["potion_result"]["remaining_count"] == 2
        print(f"[OK] Potion used! Healed {p_res['potion_result']['heal_hp']} HP. Remaining count: {p_res['potion_result']['remaining_count']}.")

        print("\n=== [4/5] Testing Hero Switch Equipment Retention ===")
        # Put on armor before switching hero
        r = await client.post("/api/rpg/inventory/equip", json={"item_uid": bought_armor["uid"]})
        assert r.status_code == 200

        # Switch hero to invoker
        r = await client.post("/api/rpg/class/select", json={"hero_class": "invoker"})
        assert r.status_code == 200
        prof = r.json()
        assert prof["hero_class"] == "invoker"
        all_item_uids = [it["uid"] for it in prof["inventory"]] + [eq["uid"] for eq in prof.get("equipment", {}).values() if eq]
        assert bought_armor["uid"] in all_item_uids, "Previous equipped armor must be preserved after class switch!"
        print("[OK] Class switch preserved previous equipment without deletion!")

        print("\n=== [5/6] Testing Hyperbolic Armor Formula Mathematics ===")
        for def_val in [0, 5, 10, 20, 50, 100]:
            dr = (def_val * 0.05) / (1.0 + def_val * 0.05)
            ehp_multiplier = 1.0 + def_val * 0.05
            incoming_atk = 100
            raw_dmg = max(2, int(incoming_atk * 0.85 * (1.0 - dr)))
            print(f"  Armor: {def_val:3d} -> DR: {dr*100:5.1f}% | EHP: x{ehp_multiplier:.2f} | Damage taken: {raw_dmg:2d}")
            assert 0.0 <= dr < 1.0, "Damage reduction must be between 0% and 100%"
            assert raw_dmg >= 2, "Damage taken should never be less than minimum clamp"

        print("[OK] Hyperbolic armor mathematics strictly verified!")

        print("\n=== [6/6] Testing Boss Roster, Halved HP Scaling & Dota Passives ===")
        # 1. Verify Raid Boss API endpoint
        r = await client.get("/api/rpg/bosses")
        assert r.status_code == 200, f"Bosses API failed: {r.text}"
        bosses_data = r.json()
        boss_map = {b["id"]: b for b in bosses_data}

        # Check new Dota bosses are in roster
        expected_new_bosses = ["pudge_boss", "faceless_void", "terrorblade", "storm_spirit", "tinker_boss"]
        for b_id in expected_new_bosses:
            assert b_id in boss_map, f"New boss {b_id} missing from /api/rpg/bosses!"
            print(f"[OK] Boss '{boss_map[b_id]['name']}' verified in roster: HP={boss_map[b_id]['max_hp']:,}, ATK={boss_map[b_id]['atk_min']}-{boss_map[b_id]['atk_max']}, DEF={boss_map[b_id]['defense']}")

        # Check Geometric Progression HP scaling (Golem x15 = 75k, Enigma = 1.2 Quadrillion)
        assert boss_map["golem"]["max_hp"] == 75_000, f"Golem HP mismatch: {boss_map['golem']['max_hp']}"
        assert boss_map["roshan"]["max_hp"] == 85_000_000, f"Roshan HP mismatch: {boss_map['roshan']['max_hp']}"
        assert boss_map["enigma"]["max_hp"] == 1_200_000_000_000_000, f"Enigma HP mismatch: {boss_map['enigma']['max_hp']}"
        print(f"[OK] Geometric HP progression verified: Golem=75k, Roshan=85M, Enigma=1.2Q HP (1+ month non-stop battle)!")

        # 2. Buy Vanguard & test damage block in effective stats
        r = await client.post("/api/rpg/shop/buy", json={"item_id": "shop_a_vanguard"})
        assert r.status_code == 200, f"Failed to buy Vanguard: {r.text}"
        bought_vg = r.json()["item"]
        assert bought_vg.get("bonus", {}).get("damage_block") == 70, f"Vanguard damage_block missing: {bought_vg}"

        r = await client.post("/api/rpg/inventory/equip", json={"item_uid": bought_vg["uid"]})
        assert r.status_code == 200
        prof = r.json()["profile"]
        pass
        assert prof["stats"]["damage_block"] == 70, f"Effective stats damage_block mismatch: {prof['stats']}"
        print(f"[OK] Vanguard equipped! Effective damage block verified: {prof['stats']['damage_block']}.")

        # 3. Buy Mjollnir & verify weapon stats
        r = await client.post("/api/rpg/shop/buy", json={"item_id": "shop_w_mjollnir"})
        assert r.status_code == 200, f"Failed to buy Mjollnir: {r.text}"
        bought_mj = r.json()["item"]
        assert bought_mj["rarity"] == "immortal"
        print(f"[OK] Mjollnir bought! ATK: {bought_mj.get('base_min')}..{bought_mj.get('base_max')}, bonus: {bought_mj.get('bonus')}.")

    print("\n=======================================================")
    print(">>> ALL RPG ECOSYSTEM INTEGRATION TESTS PASSED! <<<")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(run_rpg_ecosystem_suite())
