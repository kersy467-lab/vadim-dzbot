"""
Unit tests for Step 7: Dota 2 Creeps Bestiary, 2D State Machine AI, and Pack Auras.
Specification 3.0.0-ULTIMATE (Volume VI).
"""
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
from backend.db.crud.rpg.creeps import DOTA_BESTIARY_CATALOG
from backend.db.crud.rpg.creeps_ai import (
    create_creep_instance,
    update_creep_ai_state,
    apply_creep_auras,
    handle_creep_death,
    AGGRO_RADIUS,
    LEASH_RADIUS,
)


def test_creeps_bestiary_suite():
    asyncio.run(run_creeps_bestiary_suite())


async def run_creeps_bestiary_suite():
    await init_db()
    print("\n=== [1/4] Testing Creeps Catalog (Volume VI, 6.2) ===")
    assert "melee_creep" in DOTA_BESTIARY_CATALOG
    assert "ranged_creep" in DOTA_BESTIARY_CATALOG
    assert "mega_creep" in DOTA_BESTIARY_CATALOG
    assert "centaur_conqueror" in DOTA_BESTIARY_CATALOG
    assert "alpha_wolf" in DOTA_BESTIARY_CATALOG
    assert "satyr_tormenter" in DOTA_BESTIARY_CATALOG
    assert "mud_golem" in DOTA_BESTIARY_CATALOG
    assert "shard_golem" in DOTA_BESTIARY_CATALOG

    # Verify canonical stats
    mc = DOTA_BESTIARY_CATALOG["melee_creep"]
    assert mc["hp"] == 280 and mc["attack"] == 24 and mc["speed"] == 160

    rc = DOTA_BESTIARY_CATALOG["ranged_creep"]
    assert rc["hp"] == 180 and rc["attack"] == 36 and rc["attack_range"] == 320

    mega = DOTA_BESTIARY_CATALOG["mega_creep"]
    assert mega["hp"] == 1400 and mega["armor"] == 14 and mega["attack"] == 95 and mega["micro_stun_immune"]

    cent = DOTA_BESTIARY_CATALOG["centaur_conqueror"]
    assert cent["hp"] == 950 and cent["ability"]["id"] == "war_stomp" and cent["ability"]["radius"] == 160

    wolf = DOTA_BESTIARY_CATALOG["alpha_wolf"]
    assert wolf["hp"] == 600 and wolf["aura"]["damage_bonus_pct"] == 30.0

    satyr = DOTA_BESTIARY_CATALOG["satyr_tormenter"]
    assert satyr["hp"] == 800 and satyr["ability"]["damage"] == 260

    golem = DOTA_BESTIARY_CATALOG["mud_golem"]
    assert golem["on_death"]["action"] == "split_into_shards" and golem["on_death"]["count"] == 2
    print("[OK] All 8 creep archetypes and canonical stats validated.")

    print("\n=== [2/4] Testing 2D State Machine AI Transitions ===")
    # 1. SPAWN -> IDLE -> CHASE -> ATTACK -> COOLDOWN
    creep = create_creep_instance("melee_creep", x=0.0, y=0.0)
    assert creep["ai_state"] == "SPAWN"

    # Step 1: Wait out spawn delay
    update_creep_ai_state(creep, player_x=1000.0, player_y=1000.0, dt=0.6)
    assert creep["ai_state"] == "IDLE"

    # Step 2: Player enters aggro radius (300px <= 450px) -> CHASE
    update_creep_ai_state(creep, player_x=300.0, player_y=0.0, dt=0.1)
    assert creep["ai_state"] == "CHASE"

    # Step 3: Moves in attack range (50px <= 60px) -> ATTACK
    creep["x"] = 260.0  # 40px away from 300.0
    res_atk = update_creep_ai_state(creep, player_x=300.0, player_y=0.0, dt=0.1)
    assert creep["ai_state"] == "ATTACK"

    # Step 4: Executes attack, enters COOLDOWN
    res_exec = update_creep_ai_state(creep, player_x=300.0, player_y=0.0, dt=0.1)
    assert res_exec["action"] == "attack"
    assert res_exec["data"]["damage"] == 24
    assert creep["ai_state"] == "COOLDOWN"

    # 2. Centaur War Stomp Cast
    centaur = create_creep_instance("centaur_conqueror", x=0.0, y=0.0)
    centaur["ai_state"] = "CHASE"
    # Player at distance 120px (<= 160px) -> casts War Stomp
    res_stomp = update_creep_ai_state(centaur, player_x=120.0, player_y=0.0, dt=0.1)
    assert res_stomp["action"] == "cast_ability"
    assert res_stomp["data"]["ability_id"] == "war_stomp"
    assert res_stomp["data"]["stun_duration"] == 1.5
    print("[OK] State machine transitions and ability casts validated.")

    print("\n=== [3/4] Testing Alpha Wolf Aura & Mud Golem Death Split ===")
    # 1. Pack Leader Aura (+30% attack)
    pack = [
        create_creep_instance("melee_creep"),
        create_creep_instance("alpha_wolf")
    ]
    pack = apply_creep_auras(pack)
    assert pack[0]["effective_attack"] == 32  # ceil(24 * 1.30) = 32
    assert "pack_leader" in pack[0]["active_auras"]

    # When wolf dies, aura drops
    pack[1]["is_alive"] = False
    pack = apply_creep_auras(pack)
    assert pack[0]["effective_attack"] == 24
    assert "pack_leader" not in pack[0]["active_auras"]
    print("[OK] Pack Leader aura apply and removal validated.")

    # 2. Mud Golem death split
    mud = create_creep_instance("mud_golem", x=100.0, y=100.0)
    split_res = handle_creep_death(mud)
    assert split_res["split"] is True
    assert len(split_res["spawned_creeps"]) == 2
    assert split_res["spawned_creeps"][0]["type_id"] == "shard_golem"
    assert split_res["spawned_creeps"][1]["type_id"] == "shard_golem"
    print("[OK] Mud Golem split into 2 Shard Golems validated.")

    print("\n=== [4/4] Testing Creeps HTTP Endpoints ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/rpg/creeps/bestiary
        r_best = await client.get("/api/rpg/creeps/bestiary")
        assert r_best.status_code == 200
        data = r_best.json()
        assert "catalog" in data and "melee_creep" in data["catalog"]
        assert data["aggro_radius"] == AGGRO_RADIUS

        # POST /api/rpg/creeps/spawn
        r_spawn = await client.post("/api/rpg/creeps/spawn", json={"type_id": "satyr_tormenter", "x": 50, "y": 50})
        assert r_spawn.status_code == 200
        spawned = r_spawn.json()
        assert spawned["type_id"] == "satyr_tormenter"
        assert spawned["hp"] == 800

        # POST /api/rpg/creeps/simulate_tick
        tick_payload = {
            "creeps": [spawned],
            "player_x": 100.0,
            "player_y": 50.0,
            "dt": 0.6
        }
        r_tick = await client.post("/api/rpg/creeps/simulate_tick", json=tick_payload)
        assert r_tick.status_code == 200
        assert "creeps" in r_tick.json()

        # POST /api/rpg/creeps/split
        r_split = await client.post("/api/rpg/creeps/split", json={"creep": mud})
        assert r_split.status_code == 200
        assert r_split.json()["split"] is True
        print("[OK] All Creeps Bestiary HTTP endpoints validated.")

    print("\n=== ALL CREEPS BESTIARY & AI TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    test_creeps_bestiary_suite()
