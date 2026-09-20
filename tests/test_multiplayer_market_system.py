"""
Unit tests for Step 6: Multiplayer Systems, Threat Engine, Party Synergies,
World Titan Roshan (50M HP), and P2P Marketplace.
Specification 3.0.0-ULTIMATE (Volume IX).
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
from backend.db.session import init_db, get_db_session
from backend.db.crud.rpg.character import get_or_create_rpg_character
from backend.db.crud.rpg.multiplayer_engine import (
    calculate_player_threat,
    determine_boss_target,
    calculate_party_synergies,
)
from backend.db.crud.rpg.world_boss_market import (
    get_world_boss_status,
    record_world_boss_attack,
    reset_world_boss,
    get_market_listings,
    list_item_for_sale,
    cancel_market_listing,
    buy_market_item,
    MARKET_FEE_PCT,
    DEFAULT_WORLD_BOSS_HP,
)


def test_multiplayer_market_suite():
    asyncio.run(run_multiplayer_market_suite())


async def run_multiplayer_market_suite():
    await init_db()
    print("\n=== [1/4] Testing Threat Engine & Party Synergies (Volume IX, 9.1 & 9.2) ===")

    # 1. Threat formula: (Dmg * 1.0) + (Taunt * 4.0) + (1000 / Dist) + (Heal * 0.6)
    # Dmg=1000, Taunt=1.0, Dist=100, Heal=500 -> 1000 + 4 + 10 + 300 = 1314.0
    threat_calc = calculate_player_threat(damage_dealt=1000, taunt_mult=1.0, distance=100.0, heal_provided=500.0)
    assert threat_calc == 1314.0, f"Expected 1314.0, got {threat_calc}"

    threats = {
        "pudge_tank": calculate_player_threat(damage_dealt=400, taunt_mult=500.0, distance=50.0),
        "pa_carry": calculate_player_threat(damage_dealt=1800, taunt_mult=1.0, distance=150.0),
    }
    target = determine_boss_target(threats)
    # Pudge: 400 + 2000 + 20 = 2420; PA: 1800 + 4 + 6.67 = 1810.67
    assert target == "pudge_tank", f"Expected pudge_tank as boss target, got {target}"
    print("[OK] Threat engine formula and target determination verified.")

    # 2. Party Synergies
    # Holy Trinity: Tank + Carry + Mage
    syn_trinity = calculate_party_synergies(["pudge", "juggernaut", "invoker"])
    active_ids = [s["id"] for s in syn_trinity["active_synergies"]]
    assert "holy_trinity" in active_ids
    assert syn_trinity["party_damage_bonus_pct"] == 35.0
    assert syn_trinity["incoming_damage_reduction_pct"] == 20.0

    # Dual Whirlwind: 2+ Agility
    syn_agi = calculate_party_synergies(["juggernaut", "phantom_assassin"])
    assert "dual_whirlwind" in [s["id"] for s in syn_agi["active_synergies"]]
    assert syn_agi["move_speed_bonus_pct"] == 25.0
    assert syn_agi["dodge_bonus_pct"] == 15.0

    # Wall of Flesh: 2+ Strength
    syn_str = calculate_party_synergies(["pudge", "wraith_king"])
    assert "wall_of_flesh" in [s["id"] for s in syn_str["active_synergies"]]
    assert syn_str["regen_shield_hp_pct"] == 15.0

    # Arcane Rift: 2+ Intelligence
    syn_int = calculate_party_synergies(["invoker", "leshrac"])
    assert "arcane_rift" in [s["id"] for s in syn_int["active_synergies"]]
    assert syn_int["mp_regen_bonus_pct"] == 30.0
    assert syn_int["cooldown_reduction_pct"] == 15.0
    print("[OK] All 4 party synergies verified.")

    print("\n=== [2/4] Testing World Titan Roshan (50M HP) (Volume IX, 9.3) ===")
    reset_world_boss()
    status = get_world_boss_status()
    assert status["max_hp"] == DEFAULT_WORLD_BOSS_HP
    assert status["current_hp"] == 50_000_000
    assert status["hp_pct"] == 100.0
    assert not status["is_defeated"]

    # Attack 1: Deal 15M damage (30% total) -> triggers 25% milestone
    atk1 = record_world_boss_attack(user_id=1, user_name="Алексей", damage=15_000_000)
    assert atk1["success"]
    assert len(atk1["newly_unlocked_milestones"]) == 1
    assert atk1["newly_unlocked_milestones"][0]["milestone_pct"] == 25
    assert atk1["boss_status"]["current_hp"] == 35_000_000

    # Attack 2: Deal 35M damage -> Defeats World Roshan, triggers 50%, 75%, 100%
    atk2 = record_world_boss_attack(user_id=2, user_name="Иван", damage=35_000_000)
    assert atk2["success"]
    assert atk2["boss_status"]["is_defeated"]
    assert atk2["boss_status"]["current_hp"] == 0
    milestone_pcts = [m["milestone_pct"] for m in atk2["newly_unlocked_milestones"]]
    assert 50 in milestone_pcts and 75 in milestone_pcts and 100 in milestone_pcts

    # Further attack rejected when defeated
    atk3 = record_world_boss_attack(user_id=1, user_name="Алексей", damage=1000)
    assert not atk3["success"]
    reset_world_boss()
    print("[OK] World Titan Roshan 50M HP, milestones and rewards verified.")

    print("\n=== [3/4] Testing P2P Marketplace CRUD (Volume IX, 9.4) ===")
    async for session in get_db_session():
        char1 = await get_or_create_rpg_character(session, user_id=1)
        char2 = await get_or_create_rpg_character(session, user_id=2)

        # Setup items and funds
        char1.inventory = [
            {"uid": "item_mkt_1", "name": "Кинжал Дагон", "slot": "weapon", "rarity": "mythic", "attack": 250},
            {"uid": "item_mkt_2", "name": "Кираса Шторма", "slot": "armor", "rarity": "legendary", "defense": 60}
        ]
        char1.gold = 500
        char2.gold = 5000
        char2.inventory = []
        await session.commit()

        # List item 1 for 1000 gold
        list_res = await list_item_for_sale(session, char1, "item_mkt_1", price=1000, currency="gold", user_name="Продавец 1")
        assert list_res["success"]
        listing_id = list_res["listing"]["listing_id"]
        assert len(char1.inventory) == 1

        # Check listings query
        listings = get_market_listings(rarity="mythic")
        assert len(listings) == 1
        assert listings[0]["item"]["uid"] == "item_mkt_1"

        # Buyer purchases item
        buy_res = await buy_market_item(session, char2, listing_id)
        assert buy_res["success"]
        assert buy_res["price_paid"] == 1000
        assert buy_res["fee_taken"] == 50  # 5% fee
        assert buy_res["seller_payout"] == 950  # 95% payout
        assert char2.gold == 4000
        assert len(char2.inventory) == 1
        assert char2.inventory[0]["uid"] == "item_mkt_1"

        # Check seller received payout
        await session.refresh(char1)
        assert char1.gold == 1450  # 500 + 950

        # Cancel listing test
        list_res2 = await list_item_for_sale(session, char1, "item_mkt_2", price=500, currency="gold")
        cancel_res = await cancel_market_listing(session, char1, list_res2["listing"]["listing_id"])
        assert cancel_res["success"]
        assert len(char1.inventory) == 1
        assert char1.inventory[0]["uid"] == "item_mkt_2"
        break

    print("[OK] P2P Marketplace listing, 5% fee, transfer and cancellation verified.")

    print("\n=== [4/4] Testing Multiplayer & Market HTTP Endpoints ===")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/rpg/multiplayer/synergies
        r_syn = await client.get("/api/rpg/multiplayer/synergies?classes=pudge,juggernaut,invoker")
        assert r_syn.status_code == 200
        assert r_syn.json()["party_damage_bonus_pct"] == 35.0

        # POST /api/rpg/multiplayer/threat/calculate
        r_threat = await client.post("/api/rpg/multiplayer/threat/calculate", json={
            "players": {
                "t1": {"damage_dealt": 100, "taunt_mult": 200.0, "distance": 10.0},
                "c1": {"damage_dealt": 2000, "taunt_mult": 1.0, "distance": 300.0}
            }
        })
        assert r_threat.status_code == 200
        assert "target_player_id" in r_threat.json()

        # GET /api/rpg/world_boss/status
        r_wb = await client.get("/api/rpg/world_boss/status")
        assert r_wb.status_code == 200
        assert r_wb.json()["max_hp"] == DEFAULT_WORLD_BOSS_HP

        # POST /api/rpg/world_boss/attack
        r_atk = await client.post("/api/rpg/world_boss/attack", json={"damage": 5000})
        assert r_atk.status_code == 200
        assert r_atk.json()["damage_dealt"] == 5000

        # GET /api/rpg/market/listings
        r_mkt = await client.get("/api/rpg/market/listings")
        assert r_mkt.status_code == 200
        assert "listings" in r_mkt.json()
        assert r_mkt.json()["fee_pct"] == 5.0
        print("[OK] All Multiplayer & Marketplace HTTP endpoints verified.")

    print("\n=== ALL MULTIPLAYER & MARKET TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    test_multiplayer_market_suite()
