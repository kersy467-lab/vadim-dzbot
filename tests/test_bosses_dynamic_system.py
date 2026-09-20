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
from backend.db.crud.rpg.bosses_engine import (
    BOSS_DIFFICULTIES,
    DOTA_BOSS_CATALOG,
    calculate_enrage_multiplier,
    get_boss_phase_state,
    calculate_boss_dynamic_damage,
)


def test_bosses_dynamic_suite():
    asyncio.run(run_bosses_dynamic_suite())


async def run_bosses_dynamic_suite():
    await init_db()
    print("\n=== [1/4] Testing Boss Difficulties Config (Volume VII, 7.1) ===")
    assert "normal" in BOSS_DIFFICULTIES
    assert "heroic" in BOSS_DIFFICULTIES
    assert "mythic" in BOSS_DIFFICULTIES
    assert "nightmare" in BOSS_DIFFICULTIES

    normal = BOSS_DIFFICULTIES["normal"]
    heroic = BOSS_DIFFICULTIES["heroic"]
    mythic = BOSS_DIFFICULTIES["mythic"]
    nightmare = BOSS_DIFFICULTIES["nightmare"]

    assert normal["hp_mult"] == 1.0 and normal["atk_mult"] == 1.0 and normal["mythic_drop_pct"] == 2.0
    assert heroic["hp_mult"] == 2.6 and heroic["atk_mult"] == 1.8 and heroic["reward_mult"] == 2.8 and heroic["mythic_drop_pct"] == 8.0
    assert mythic["hp_mult"] == 6.5 and mythic["atk_mult"] == 3.2 and mythic["reward_mult"] == 7.0 and mythic["mythic_drop_pct"] == 25.0 and mythic["immortal_drop_pct"] == 6.0
    assert nightmare["hp_mult"] == 16.0 and nightmare["atk_mult"] == 5.8 and nightmare["reward_mult"] == 18.0 and nightmare["mythic_drop_pct"] == 65.0 and nightmare["immortal_drop_pct"] == 22.0
    print("[OK] All 4 difficulty tiers validated.")

    print("\n=== [2/4] Testing Boss Roster & Telegraph Attacks (Volume VII, 7.2) ===")
    roshan = DOTA_BOSS_CATALOG["roshan"]
    assert roshan["base_hp"] == 2_800_000
    assert roshan["base_atk"] == 850
    assert roshan["special_drop"] == "Aegis of the Immortal"
    r_attacks = {atk["id"]: atk for atk in roshan["telegraph_attacks"]}
    assert "slam" in r_attacks and r_attacks["slam"]["radius"] == 280 and r_attacks["slam"]["damage"] == 1800
    assert "fire_breath" in r_attacks and "spellblock" in r_attacks

    tormentor = DOTA_BOSS_CATALOG["tormentor"]
    t_attacks = {atk["id"]: atk for atk in tormentor["telegraph_attacks"]}
    assert "mirror_reflection" in t_attacks and t_attacks["mirror_reflection"]["reflect_pct"] == 35
    assert "psionic_barrier" in t_attacks and t_attacks["psionic_barrier"]["shield_amount"] == 300_000

    primal = DOTA_BOSS_CATALOG["primal_beast"]
    p_attacks = {atk["id"]: atk for atk in primal["telegraph_attacks"]}
    assert "onslaught" in p_attacks and p_attacks["onslaught"]["damage"] == 3500 and p_attacks["onslaught"]["telegraph_time"] == 3.0
    assert "trample" in p_attacks

    lich = DOTA_BOSS_CATALOG["archlich"]
    l_attacks = {atk["id"]: atk for atk in lich["telegraph_attacks"]}
    assert "chain_frost" in l_attacks and l_attacks["chain_frost"]["max_bounces"] == 10 and l_attacks["chain_frost"]["bounce_dmg_growth_pct"] == 20
    print("[OK] Boss roster and telegraph attacks validated.")

    print("\n=== [3/4] Testing Dynamic Math: Enrage, Phases & Formula ===")
    # Enrage
    assert calculate_enrage_multiplier(0.0) == 1.0
    assert calculate_enrage_multiplier(7.9) == 1.0
    assert calculate_enrage_multiplier(8.0) == 1.14
    assert calculate_enrage_multiplier(16.0) == 1.28
    assert calculate_enrage_multiplier(24.0) == 1.42
    # Pacifier constellation
    assert calculate_enrage_multiplier(16.0, pacifier_level=1) == 1.2408
    assert calculate_enrage_multiplier(16.0, pacifier_level=5) == 1.084

    # Phases
    p1 = get_boss_phase_state(900, 1000)
    assert p1["phase"] == 1 and p1["phase_mult"] == 1.0 and p1["shield_pct"] == 0.0 and not p1["spawns_adds"] and not p1["fire_trails"]

    p2 = get_boss_phase_state(500, 1000)
    assert p2["phase"] == 2 and p2["phase_mult"] == 1.25 and p2["shield_pct"] == 0.25 and p2["spawns_adds"] and not p2["fire_trails"]

    p3 = get_boss_phase_state(200, 1000)
    assert p3["phase"] == 3 and p3["phase_mult"] == 1.55 and p3["shield_pct"] == 0.0 and not p3["spawns_adds"] and p3["fire_trails"] and p3["atk_speed_bonus_pct"] == 50

    # Master damage formula
    dmg_norm = calculate_boss_dynamic_damage(base_atk=1000, difficulty="normal", target_defense=100)
    assert dmg_norm == 900

    dmg_heroic = calculate_boss_dynamic_damage(base_atk=1000, difficulty="heroic", target_defense=0)
    assert dmg_heroic == 1800

    dmg_mythic = calculate_boss_dynamic_damage(base_atk=1000, difficulty="mythic", target_defense=0)
    assert dmg_mythic == 3200

    dmg_night = calculate_boss_dynamic_damage(base_atk=1000, difficulty="nightmare", target_defense=0)
    assert dmg_night == 5800

    dmg_complex = calculate_boss_dynamic_damage(
        base_atk=1000,
        difficulty="normal",
        elapsed_seconds=16.0,
        current_hp=20,
        max_hp=100,
        party_size=3,
        target_defense=0
    )
    # 1000 * 1.0 * 1.28 * 1.5 * 1.55 = 2976
    assert dmg_complex == 2976

    dmg_min = calculate_boss_dynamic_damage(base_atk=50, target_defense=999999)
    assert dmg_min == 1
    print("[OK] Enrage, phase transitions and master dynamic damage formula validated.")

    print("\n=== [4/4] Testing HTTP Endpoints ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/rpg/bosses/dynamic
        r_dyn = await client.get("/api/rpg/bosses/dynamic")
        assert r_dyn.status_code == 200
        dyn_data = r_dyn.json()
        assert "bosses" in dyn_data and "roshan" in dyn_data["bosses"]
        assert "difficulties" in dyn_data and "normal" in dyn_data["difficulties"]
        assert len(dyn_data["phases"]) == 3
        print("[OK] GET /api/rpg/bosses/dynamic returned full catalog and phases.")

        # POST /api/rpg/bosses/simulate_damage
        sim_payload = {
            "boss_id": "roshan",
            "difficulty": "heroic",
            "elapsed_seconds": 16.0,
            "current_hp": 250000,
            "max_hp": 1000000,
            "party_size": 2,
            "target_defense": 200
        }
        r_sim = await client.post("/api/rpg/bosses/simulate_damage", json=sim_payload)
        assert r_sim.status_code == 200
        sim_res = r_sim.json()
        assert sim_res["boss_id"] == "roshan"
        assert sim_res["difficulty"] == "heroic"
        assert sim_res["difficulty_mult"] == 1.8
        assert sim_res["enrage_mult"] == 1.28
        assert sim_res["phase"]["phase"] == 3
        assert sim_res["party_mult"] == 1.25
        assert sim_res["damage"] > 0
        print(f"[OK] POST /api/rpg/bosses/simulate_damage calculated damage={sim_res['damage']}.")

        # GET /api/rpg/bosses (backward compatibility)
        r_coop = await client.get("/api/rpg/bosses")
        assert r_coop.status_code == 200
        assert isinstance(r_coop.json(), list)
        print("[OK] GET /api/rpg/bosses backward compatibility confirmed.")

    print("\n=== ALL BOSSES DYNAMIC TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    test_bosses_dynamic_suite()
