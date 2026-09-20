import os
import sys
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_rpg.db"

from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.session import get_db_session, init_db
from backend.db.models import User
from backend.db.crud.rpg import get_or_create_rpg_character
from backend.api.game_rooms import RPGPvPRoom, RPGCoopBossRoom


async def run_balance_and_wave_tests():
    print("\n=== [1/4] Testing Cumulative Wave Sync & Floor Scaling via API ===")
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Reset character state for clean test baseline
        gen = get_db_session()
        session = await anext(gen)
        try:
            user = await session.get(User, 1)
            if not user:
                user = User(id=1, tg_id=101, username="testhero", full_name="Test Hero", role="student")
                session.add(user)
                await session.commit()
            char = await get_or_create_rpg_character(session, user_id=1)
            char.dungeon_cleared = 0
            char.dungeon_floor = 1
            await session.commit()
        finally:
            await session.close()

        # Step A: Wave 1 clear
        r = await client.post("/api/rpg/dungeon/wave", json={"wave_cleared": 1, "earned_gold": 28, "earned_xp": 18})
        assert r.status_code == 200
        d1 = r.json()
        assert d1["wave_cleared"] == 1
        assert d1["floor"] == 1
        print(f"[OK] Wave 1 synced: cleared={d1['wave_cleared']}, floor={d1['floor']}")

        # Step B: Wave 20 clear (Floor 1 Boss)
        r = await client.post("/api/rpg/dungeon/wave", json={"wave_cleared": 20, "earned_gold": 180, "earned_xp": 132})
        assert r.status_code == 200
        d20 = r.json()
        assert d20["wave_cleared"] == 20
        assert d20["floor"] == 2, f"Expected Floor 2 after wave 20, got {d20['floor']}"
        print(f"[OK] Floor 1 Boss cleared! Advanced to Floor {d20['floor']} (cumulative wave {d20['wave_cleared']})")

        # Step C: Wave 21 clear (Floor 2 Wave 1)
        r = await client.post("/api/rpg/dungeon/wave", json={"wave_cleared": 21, "earned_gold": 30, "earned_xp": 20})
        assert r.status_code == 200
        d21 = r.json()
        assert d21["wave_cleared"] == 21
        assert d21["floor"] == 2
        print(f"[OK] Floor 2 Wave 1 synced cleanly: cleared={d21['wave_cleared']}, floor={d21['floor']}")

        # Step D: Wave 40 clear (Floor 2 Boss)
        r = await client.post("/api/rpg/dungeon/wave", json={"wave_cleared": 40, "earned_gold": 340, "earned_xp": 250})
        assert r.status_code == 200
        d40 = r.json()
        assert d40["wave_cleared"] == 40
        assert d40["floor"] == 3
        print(f"[OK] Floor 2 Boss cleared! Advanced to Floor {d40['floor']} (cumulative wave {d40['wave_cleared']})")

    print("\n=== [2/4] Testing PvP Room Hyperbolic Armor Scaling ===")
    pvp = RPGPvPRoom(room_id="test_pvp_room", host_name="HostPlayer", host_tg_id=100, opponent_name="OpponentPlayer", opponent_tg_id=200)
    pvp.status = "playing"
    pvp.turn = "host"
    pvp.players["host"]["min_atk"] = 40
    pvp.players["host"]["max_atk"] = 40
    pvp.players["host"]["crit_chance"] = 0
    pvp.players["opponent"]["defense"] = 20
    pvp.players["opponent"]["is_defending"] = False
    pvp.players["opponent"]["dodge_chance"] = 0

    # Host attacks opponent: base_dmg = 40, opponent def = 20
    # Expected hyperbolic DR = (20 * 0.05) / (1 + 20 * 0.05) = 1.0 / 2.0 = 50%
    # Expected final_dmg = max(5, int(40 * 0.5)) = 20
    hp_before = pvp.players["opponent"]["hp"]
    ok, msg = pvp.make_move(100, {"action": "attack"})
    assert ok is True, f"Move failed: {msg}"
    dmg_dealt = hp_before - pvp.players["opponent"]["hp"]
    assert dmg_dealt == 20, f"Expected 20 damage (50% DR on 40 atk), got {dmg_dealt}"
    print(f"[OK] PvP Hyperbolic Armor verified: 40 Atk vs 20 Def -> {dmg_dealt} damage dealt (exactly 50% DR)!")

    print("\n=== [3/4] Testing Co-op Boss 3-Player Round-Robin & Hyperbolic Armor ===")
    coop = RPGCoopBossRoom("test_coop_room", 101, "Hero1", boss_id="roshan")
    coop.add_coop_player(102, "Hero2")
    coop.add_coop_player(103, "Hero3")
    coop.status = "playing"
    coop.turn = "host"

    coop.players["host"]["hp"] = 150000
    coop.players["host"]["hp_max"] = 150000
    coop.players["host"]["min_atk"] = 50
    coop.players["host"]["max_atk"] = 50
    coop.players["host"]["crit_chance"] = 0
    coop.players["host"]["defense"] = 10

    coop.players["player_2"]["hp"] = 1500
    coop.players["player_2"]["hp_max"] = 1500
    coop.players["player_2"]["min_atk"] = 50
    coop.players["player_2"]["max_atk"] = 50
    coop.players["player_2"]["crit_chance"] = 0
    coop.players["player_2"]["defense"] = 10

    coop.players["player_3"]["hp"] = 1500
    coop.players["player_3"]["hp_max"] = 1500
    coop.players["player_3"]["min_atk"] = 50
    coop.players["player_3"]["max_atk"] = 50
    coop.players["player_3"]["crit_chance"] = 0
    coop.players["player_3"]["defense"] = 10
    coop.boss["defense"] = 16

    # Turn 1: Hero 1 acts
    assert coop.turn == "host"
    hp_before = coop.boss["hp"]
    ok, _ = coop.make_move(101, "attack")
    assert ok is True
    # Hero 50 Atk vs Boss 16 Def: b_dr = (16*0.05)/(1+16*0.05) = 0.8/1.8 = 0.4444, dmg = int(50*0.5555) = 27
    dmg_to_boss = hp_before - coop.boss["hp"]
    assert dmg_to_boss == 27, f"Expected 27 damage to boss, got {dmg_to_boss}"
    assert coop.turn == "player_2", f"Expected turn player_2, got {coop.turn}"

    # Turn 2: Hero 2 acts
    ok, _ = coop.make_move(102, "attack")
    assert ok is True
    assert coop.turn == "player_3", f"Expected turn player_3, got {coop.turn}"

    # Turn 3: Hero 3 acts -> Round completes -> Boss retaliates on hero 1 -> turn cycles back to host!
    hero1_hp_before = coop.players["host"]["hp"]
    ok, _ = coop.make_move(103, "attack")
    assert ok is True
    hero1_dmg = hero1_hp_before - coop.players["host"]["hp"]
    assert hero1_dmg > 0, f"Expected boss damage on Hero 1, got {hero1_dmg}"
    assert coop.turn == "host", f"Expected turn to cycle back to host, got {coop.turn}"
    print(f"[OK] 3-Hero Round-Robin cycle completed: Hero1 -> Hero2 -> Hero3 -> Boss (Hit Hero1 for {hero1_dmg} dmg) -> Hero1!")

    print("\n=== [4/4] Testing Fast-Sim Tactical Battle with Hyperbolic DR ===")
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post("/api/rpg/dungeon/wave", json={})
        assert r.status_code == 200
        data = r.json()
        assert "victory" in data
        assert "combat_log" in data
        assert len(data["combat_log"]) > 0
        print(f"[OK] Fast-Sim combat completed: {len(data['combat_log'])} combat events generated with hyperbolic DR.")

    print("\n=======================================================")
    print(">>> ALL BALANCE, WAVE AND ROOM TESTS PASSED (4/4)! <<<")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(run_balance_and_wave_tests())
