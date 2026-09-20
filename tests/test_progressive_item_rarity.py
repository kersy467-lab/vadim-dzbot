import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_rpg.db"

from backend.db.session import init_db, async_session_factory
from backend.db.models import RPGCharacter
from backend.db.crud.rpg.loot import generate_random_natar_item, get_floor_rarity_weights
from backend.db.crud.rpg.chests import open_wave_chest, open_boss_raid_chest
from backend.db.crud.rpg.character import get_or_create_rpg_character

async def main():
    await init_db()
    print("=== Testing Progressive Item Rarity & Floor Guarantees ===")

    # 1. Test Floor Rarity Weights
    w1 = get_floor_rarity_weights(1)
    assert w1["common"] > 0
    assert w1["uncommon"] > 0
    assert w1["rare"] > 0
    assert w1["epic"] == 0.0
    assert w1["legendary"] == 0.0
    assert w1["mythic"] == 0.0
    assert w1["immortal"] == 0.0
    print("[OK] Floor 1 weights: strictly 0% for epic, legendary, mythic, immortal.")

    w2 = get_floor_rarity_weights(2)
    assert w2["legendary"] == 0.0 and w2["mythic"] == 0.0 and w2["immortal"] == 0.0
    print("[OK] Floor 2 weights: strictly 0% for legendary, mythic, immortal.")

    w3 = get_floor_rarity_weights(3)
    assert w3["legendary"] == 0.0 and w3["mythic"] == 0.0 and w3["immortal"] == 0.0
    print("[OK] Floor 3 weights: strictly 0% for legendary, mythic, immortal.")

    w7 = get_floor_rarity_weights(7)
    assert w7["immortal"] > 0.0
    assert w7["legendary"] > 0.0
    print(f"[OK] Floor 7 weights: immortal unlocked ({w7['immortal']}%), legendary ({w7['legendary']}%).")

    # 2. Statistical Loot Generation Verification (1000 items per floor)
    f1_rarities = set()
    for _ in range(1000):
        it = generate_random_natar_item(floor=1)
        r = it.get("rarity")
        f1_rarities.add(r)
        assert r in ("common", "uncommon", "rare"), f"Unexpected rarity on floor 1: {r}"
    print(f"[OK] 1000 items on Floor 1 generated without any high-tier breaches: {f1_rarities}")

    f2_rarities = set()
    for _ in range(1000):
        it = generate_random_natar_item(floor=2)
        r = it.get("rarity")
        f2_rarities.add(r)
        assert r in ("common", "uncommon", "rare", "epic"), f"Unexpected rarity on floor 2: {r}"
    print(f"[OK] 1000 items on Floor 2 generated without any high-tier breaches: {f2_rarities}")

    f3_rarities = set()
    for _ in range(1000):
        it = generate_random_natar_item(floor=3)
        r = it.get("rarity")
        f3_rarities.add(r)
        assert r in ("common", "uncommon", "rare", "epic"), f"Unexpected rarity on floor 3: {r}"
    print(f"[OK] 1000 items on Floor 3 generated without any high-tier breaches: {f3_rarities}")

    # 3. Wave Chest Verification (Floor 1 & 2)
    async with async_session_factory() as session:
        char = await get_or_create_rpg_character(session, user_id=999999)
        char.inventory = []
        char.dungeon_floor = 1

        # Wave 10 Chest (Floor 1)
        for _ in range(50):
            chest = await open_wave_chest(session, char, wave=10)
            item_r = chest["item"]["rarity"]
            assert item_r in ("common", "uncommon", "rare"), f"Wave 10 chest gave invalid rarity: {item_r}"
        print("[OK] 50 Wave 10 chests opened: strictly common/uncommon/rare.")

        # Wave 20 Chest (Floor 1 end)
        for _ in range(50):
            chest = await open_wave_chest(session, char, wave=20)
            item_r = chest["item"]["rarity"]
            assert item_r in ("common", "uncommon", "rare"), f"Wave 20 chest gave invalid rarity: {item_r}"
        print("[OK] 50 Wave 20 chests opened: strictly common/uncommon/rare.")

        # Wave 40 Chest (Floor 2 end)
        for _ in range(50):
            chest = await open_wave_chest(session, char, wave=40)
            item_r = chest["item"]["rarity"]
            assert item_r in ("uncommon", "rare", "epic"), f"Wave 40 chest gave invalid rarity: {item_r}"
        print("[OK] 50 Wave 40 chests opened: strictly uncommon/rare/epic (zero legendary/immortal).")

        # 4. Boss Chest Verification for early bosses
        # Golem (Floor 1)
        for _ in range(20):
            golem_chest = await open_boss_raid_chest(session, char, boss_id="golem")
            assert golem_chest["item"]["rarity"] == "rare", f"Golem dropped non-rare: {golem_chest['item']['rarity']}"
        print("[OK] Golem strictly drops Rare items.")

        # Lich (Floor 2)
        for _ in range(20):
            lich_chest = await open_boss_raid_chest(session, char, boss_id="lich")
            assert lich_chest["item"]["rarity"] == "epic", f"Lich dropped non-epic: {lich_chest['item']['rarity']}"
        print("[OK] Lich strictly drops Epic items (no immortal Skadi!).")

        # Tormentor (Floor 3)
        for _ in range(20):
            tormentor_chest = await open_boss_raid_chest(session, char, boss_id="tormentor")
            assert tormentor_chest["item"]["rarity"] == "epic", f"Tormentor dropped non-epic: {tormentor_chest['item']['rarity']}"
        print("[OK] Tormentor strictly drops Epic items (no immortal Shard!).")

        # Dragon (Floor 4)
        for _ in range(20):
            dragon_chest = await open_boss_raid_chest(session, char, boss_id="dragon")
            assert dragon_chest["item"]["rarity"] == "legendary", f"Dragon dropped non-legendary: {dragon_chest['item']['rarity']}"
        print("[OK] Dragon drops Legendary items (no immortal Scale!).")

        # Roshan (Floor 7)
        roshan_rarities = set()
        for _ in range(30):
            roshan_chest = await open_boss_raid_chest(session, char, boss_id="roshan")
            roshan_rarities.add(roshan_chest["item"]["rarity"])
        assert "immortal" in roshan_rarities, "Roshan should drop immortal items!"
        print(f"[OK] Roshan drops Immortal items: {roshan_rarities}")

    print("\n=== ALL PROGRESSIVE ITEM RARITY TESTS PASSED FLAWLESSLY! ===")

if __name__ == "__main__":
    asyncio.run(main())
