import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_rpg.db"

from backend.db.session import init_db, async_session_factory
from backend.db.models import User, RPGCharacter
from backend.db.crud.rpg import (
    NATAR_HEROES,
    NATAR_ITEMS_CATALOG,
    NATAR_CREEPS_POOL,
    NATAR_FLOOR_BOSSES,
    get_or_create_rpg_character,
    serialize_character_profile,
    calculate_character_effective_stats,
    equip_item_for_character,
    upgrade_item_forge,
    sell_item_from_inventory,
    upgrade_character_base_stat,
    generate_random_natar_item,
    add_xp_and_gold_to_character,
    get_rpg_leaderboard_data,
    open_wave_chest
)
from backend.api.game_rooms import GameRoomManager, RPGPvPRoom, RPGCoopBossRoom
from backend.main import app


async def run_rpg_tests():
    print("=== [1/5] Testing natarGRP Heroes & Functional Items Catalog ===")
    assert len(NATAR_HEROES) >= 7
    for hero_id, hero in NATAR_HEROES.items():
        assert "name" in hero and "icon" in hero
        assert hero["str"] > 0 and hero["agi"] > 0 and hero["int"] > 0
        assert hero["attr"] in ["Сила", "Ловкость", "Интеллект"]
        assert "starter_weapon" in hero and "starter_armor" in hero
    print(f"[OK] {len(NATAR_HEROES)} natarGRP heroes verified: {list(NATAR_HEROES.keys())}")

    assert len(NATAR_ITEMS_CATALOG) >= 24
    rarities = {item["rarity"] for item in NATAR_ITEMS_CATALOG}
    assert "common" in rarities
    assert "uncommon" in rarities
    assert "rare" in rarities
    assert "epic" in rarities
    assert "immortal" in rarities
    for it in NATAR_ITEMS_CATALOG:
        assert "slot" in it and "bonus_desc" in it
    print(f"[OK] {len(NATAR_ITEMS_CATALOG)} functional items catalog verified across 5 rarities with clear labels.")

    print("\n=== [2/5] Testing 3-Attribute System & Chest Rewards ===")
    if os.path.exists("./data/test_rpg.db"):
        try:
            os.remove("./data/test_rpg.db")
        except Exception:
            pass
    await init_db()
    async with async_session_factory() as session:
        # Create test user
        user = User(tg_id=987654321, full_name="DotaGod", username="dotagod")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Get or create RPG character
        char = await get_or_create_rpg_character(session, user_id=user.id, preferred_class="pudge")
        assert char.user_id == user.id
        assert char.level == 1
        assert char.gold == 250
        assert char.stat_points == 2

        # Calculate stats (3 attributes + Primary bonus)
        stats = calculate_character_effective_stats(char)
        assert stats["hp_max"] >= 200
        assert stats["min_atk"] > 0
        assert stats["defense"] >= 0
        assert stats["attack_speed"] >= 1.0
        assert stats["primary_attr"] == "Сила"
        assert stats["primary_damage_bonus"] == int(stats.get("total_strength", char.strength) * 1.5)
        print(f"[OK] 3-Attribute stats calculated: HP {stats['hp_max']}, ATK {stats['min_atk']}-{stats['max_atk']} (Primary Bonus: +{stats['primary_damage_bonus']})")

        # Upgrade base stat using free stat point
        initial_str = char.strength
        ok, msg = await upgrade_character_base_stat(session, char, "str")
        assert ok is True
        assert char.strength == initial_str + 1
        assert char.stat_points == 1
        print(f"[OK] Upgraded Strength using free level-up stat point (remaining: {char.stat_points}).")

        # Spend remaining stat points then upgrade with gold
        char.stat_points = 0
        char.gold = 1000
        await session.commit()
        ok, msg = await upgrade_character_base_stat(session, char, "agi")
        assert ok is True
        assert char.agility == 10
        assert char.gold < 1000
        print("[OK] Upgraded Agility using farmed gold when stat points are 0.")

        # Test Chest Reward opening (every 10-20 waves)
        chest = await open_wave_chest(session, char, wave=10)
        assert chest["chest_name"] is not None
        assert chest["gold_reward"] > 0
        assert chest["item"] is not None
        assert len(char.inventory) >= 1
        print(f"[OK] Reward Chest opened: {chest['chest_name']} | Dropped: {chest['item']['name']} ({chest['item']['rarity']})")

        # Item Forge Upgrade (+1..+100)
        while True:
            test_item = generate_random_natar_item(floor=1)
            if test_item.get("slot") in ["weapon", "armor", "relic"]:
                break
        char.inventory = [test_item]
        char.gold = 1000
        await session.commit()

        initial_atk = test_item.get("min_atk") or test_item.get("base_min") or 0
        initial_def = test_item.get("defense") or test_item.get("base_def") or 0
        ok, msg, up_item = await upgrade_item_forge(session, char, test_item["uid"])
        assert ok is True
        assert up_item["forge_level"] == 1
        if initial_atk > 0:
            assert (up_item.get("min_atk") or up_item.get("base_min", 0)) > initial_atk
        if initial_def > 0:
            assert (up_item.get("defense") or up_item.get("base_def", 0)) > initial_def
        print(f"[OK] Item forged to +1 with stat multiplier: {up_item['name']} (+1): {up_item.get('bonus_desc')}")

        # Equip Item
        ok, msg = await equip_item_for_character(session, char, up_item["uid"])
        assert ok is True
        equipped_uids = [eq_item.get("uid") for eq_item in char.equipment.values() if eq_item]
        assert up_item["uid"] in equipped_uids
        print(f"[OK] Item equipped into character slots successfully.")

        # Sell Item
        drop_item = generate_random_natar_item(floor=2)
        char.inventory = [drop_item]
        await session.commit()
        ok, msg, gold_earned = await sell_item_from_inventory(session, char, drop_item["uid"])
        assert ok is True
        assert gold_earned > 0
        assert len(char.inventory) == 0
        print(f"[OK] Item sold for {gold_earned} gold.")

        # XP and Level up (+1 stat point award)
        leveled, new_lvl = await add_xp_and_gold_to_character(session, char, xp_amount=150, gold_amount=200)
        assert leveled is True
        assert new_lvl == 2
        assert char.level == 2
        assert char.stat_points >= 1
        print(f"[OK] Leveled up to Level 2 and earned +1 free stat point (current: {char.stat_points}).")

    print("\n=== [3/5] Testing 1v1 PvP Duel Room Engine ===")
    mgr = GameRoomManager()
    pvp_room = mgr.create_room(
        host_tg_id=111,
        host_name="Папич",
        opponent_tg_id=222,
        opponent_name="Иллидан",
        game_type="rpg_duel"
    )
    assert isinstance(pvp_room, RPGPvPRoom)
    assert pvp_room.status == "waiting"

    # Opponent joins
    ok, msg = mgr.join_room(pvp_room.room_id, 222, "Иллидан")
    assert ok is True
    assert pvp_room.status == "playing"
    assert pvp_room.turn == "host"

    # Host attacks
    ok, msg = mgr.make_move(pvp_room.room_id, 111, {"action": "attack"})
    assert ok is True
    assert pvp_room.turn == "opponent"
    assert len(pvp_room.combat_log) >= 1
    print("[OK] Host attacked opponent, damage recorded in combat log.")

    # Opponent drinks potion
    ok, msg = mgr.make_move(pvp_room.room_id, 222, {"action": "potion"})
    assert ok is True
    assert pvp_room.turn == "host"
    print("[OK] Opponent healed with potion.")

    # Opponent defends
    ok, msg = mgr.make_move(pvp_room.room_id, 111, {"action": "defend"})
    assert ok is True
    assert pvp_room.players["host"]["is_defending"] is True
    print("[OK] Defensive stance activated with damage reduction.")

    print("\n=== [4/5] Testing Co-op Boss Raid Engine ===")
    coop_room = mgr.create_room(
        host_tg_id=111,
        host_name="Папич",
        opponent_tg_id=222,
        opponent_name="Головач",
        game_type="rpg_coop",
        host_color="roshan"
    )
    assert isinstance(coop_room, RPGCoopBossRoom)
    assert coop_room.boss["name"] is not None

    ok, msg = mgr.join_room(coop_room.room_id, 222, "Головач")
    assert ok is True
    assert coop_room.status == "playing"

    # Attack boss together
    initial_boss_hp = coop_room.boss["hp"]
    ok, msg = mgr.make_move(coop_room.room_id, 111, {"action": "attack"})
    assert ok is True
    assert coop_room.boss["hp"] < initial_boss_hp
    print(f"[OK] Co-op heroes attacked boss! HP decreased from {initial_boss_hp} to {coop_room.boss['hp']}")

    # 3rd player joins raid
    ok, msg = mgr.join_room(coop_room.room_id, 333, "Влад Дотный")
    assert ok is True
    assert coop_room.players["player_3"]["name"] == "Влад Дотный"
    print("[OK] 3rd player joined co-op boss raid successfully.")

    # 4th player rejected (max 3)
    ok, msg = mgr.join_room(coop_room.room_id, 444, "Лишний")
    assert ok is False
    assert "максимум 3" in msg
    print("[OK] 4th player rejected (strictly 3 max players).")

    # Round-robin boss rotation test: player 2 attacks, then player 3 attacks -> boss attacks in turn
    assert coop_room.turn == "player_2"
    ok, msg = mgr.make_move(coop_room.room_id, 222, {"action": "attack"})
    assert ok is True
    assert coop_room.turn == "player_3"

    # Player 3 attacks -> triggers Boss round-robin retaliation!
    ok, msg = mgr.make_move(coop_room.room_id, 333, {"action": "attack"})
    assert ok is True
    assert coop_room.boss_target_index > 0
    print("[OK] Round-robin boss attack triggered and cycled turn back to hero.")

    # Solo Boss Raid test (1v1 mode)
    solo_room = mgr.create_room(
        host_tg_id=111,
        host_name="СолоДотер",
        game_type="rpg_coop",
        boss_id="roshan",
        is_solo=True
    )
    assert isinstance(solo_room, RPGCoopBossRoom)
    assert solo_room.is_solo is True
    # Scaled HP: Roshan 85,000,000 * 0.45 = 38,250,000
    assert solo_room.boss["hp"] == 38250000
    solo_room.players["host"]["hp"] = 50000
    assert solo_room.players["player_2"]["tg_id"] is None
    assert solo_room.players["player_3"]["tg_id"] is None
    # 1v1 action: Host attacks -> Boss immediately retaliates -> Host turn again!
    ok, msg = mgr.make_move(solo_room.room_id, 111, {"action": "attack"})
    assert ok is True
    assert solo_room.turn == "host"
    room_dict = solo_room.to_dict(viewer_tg_id=111)
    assert room_dict["is_solo"] is True
    assert room_dict["is_your_turn"] is True
    print(f"[OK] Solo Boss Raid 1v1 verified: Scaled Boss HP ({solo_room.boss['hp']}), 1v1 immediate turn cycling.")

    print("\n=== [5/5] Testing FastAPI REST Endpoints ===")
    client = TestClient(app)

    # 1. Heroes endpoint
    res = client.get("/api/rpg/heroes")
    assert res.status_code == 200
    heroes_data = res.json()
    assert len(heroes_data) >= 7
    print(f"[OK] GET /api/rpg/heroes returned {len(heroes_data)} heroes.")

    # 2. Profile endpoint
    res = client.get("/api/rpg/profile")
    assert res.status_code == 200
    prof = res.json()
    assert "hero_class" in prof
    assert "stats" in prof
    assert "gold" in prof
    assert "stat_points" in prof
    print(f"[OK] GET /api/rpg/profile returned character profile with stat points.")

    # 3. Class select endpoint
    res = client.post("/api/rpg/class/select", json={"hero_class": "juggernaut"})
    assert res.status_code == 200
    updated_prof = res.json()
    assert updated_prof["hero_class"] == "juggernaut"
    print("[OK] POST /api/rpg/class/select successfully switched to Juggernaut.")

    # 4. Chest opening endpoint
    async with async_session_factory() as s:
        ch = await get_or_create_rpg_character(s, user_id=1)
        ch.dungeon_cleared = 10
        await s.commit()
    res = client.post("/api/rpg/chest/open", json={"wave": 10})
    assert res.status_code == 200
    chest_res = res.json()
    assert "chest_name" in chest_res
    assert "item" in chest_res
    print(f"[OK] POST /api/rpg/chest/open opened {chest_res['chest_name']} successfully.")

    # 5. Creep Wave Slaughter
    res = client.post("/api/rpg/dungeon/wave", json={})
    assert res.status_code == 200
    wave_data = res.json()
    assert "victory" in wave_data
    assert "enemy_name" in wave_data
    assert "combat_log" in wave_data
    print(f"[OK] POST /api/rpg/dungeon/wave simulated: {wave_data['enemy_name']} | Victory: {wave_data['victory']}")

    # 6. Leaderboard endpoint
    res = client.get("/api/rpg/leaderboard")
    assert res.status_code == 200
    lb = res.json()
    assert isinstance(lb, list)
    assert len(lb) >= 1
    print(f"[OK] GET /api/rpg/leaderboard returned {len(lb)} ranked players.")

    # 7. Co-op Bosses endpoint
    res = client.get("/api/rpg/bosses")
    assert res.status_code == 200
    bosses = res.json()
    assert len(bosses) >= 3
    print(f"[OK] GET /api/rpg/bosses returned {len(bosses)} raid bosses.")

    print("\n=======================================================")
    print(">>> ALL 5 natarGRP TEST SUITES PASSED FLAWLESSLY! <<<")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(run_rpg_tests())
