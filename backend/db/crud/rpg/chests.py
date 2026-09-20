import random
import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from backend.db.models import RPGCharacter
from backend.db.crud.rpg.loot import generate_random_natar_item, pick_smart_loot_item, rebuild_item_description, get_floor_rarity_weights
from backend.db.crud.rpg.chests_drops import BOSS_EXCLUSIVE_DROPS
from backend.db.crud.rpg.items_catalog import NATAR_ITEMS_CATALOG, RARITY_MULTIPLIERS
from backend.db.crud.rpg.heroes import NATAR_HEROES

BOSS_FLOORS = {
    "golem": 1, "lich": 2, "tormentor": 3, "dragon": 4,
    "pudge_boss": 5, "faceless_void": 6, "roshan": 7,
    "tidehunter": 8, "sf_boss": 9, "necrophos": 10,
    "terrorblade": 11, "invoker_boss": 12, "chaos_knight": 13,
    "dark_tormentor": 14, "storm_spirit": 15, "doom": 16,
    "primal_beast": 17, "phantom_roshan": 18, "tinker_boss": 19,
    "enigma": 20
}

async def open_wave_chest(
    session: AsyncSession,
    char: RPGCharacter,
    wave: int
) -> Dict[str, Any]:
    """
    Opens a reward chest earned every 10-20 waves!
    Uses progressive floor rarity: early floors never award legendary/immortal items.
    """
    w = max(1, wave)
    char_floor = max(1, ((w - 1) // 20) + 1)
    floor_mult = 1.0 + (char_floor - 1) * 0.10

    if char_floor >= 11:
        tier = "immortal"
        chest_name = "Божественный Сундук Бессмертных"
        chest_icon = "🌟"
        gold_reward = int((600 + w * 10) * floor_mult) + random.randint(50, 120)
        gems_reward = min(40, 15 + char_floor // 2)
        rarity_weights = {"legendary": 45.0, "mythic": 35.0, "immortal": 20.0}
    elif char_floor >= 7:
        tier = "mythic"
        chest_name = "Мифический Сундук Владыки"
        chest_icon = "👑"
        gold_reward = int((400 + w * 8) * floor_mult) + random.randint(30, 80)
        gems_reward = min(25, 10 + char_floor // 3)
        rarity_weights = {"epic": 45.0, "legendary": 45.0, "mythic": 8.0, "immortal": 2.0}
    elif char_floor >= 4:
        tier = "gold"
        chest_name = "Золотой Сундук Катакомб"
        chest_icon = "🎁"
        gold_reward = int((250 + w * 6) * floor_mult) + random.randint(25, 60)
        gems_reward = min(18, 6 + char_floor // 3)
        rarity_weights = {"rare": 45.0, "epic": 48.0, "legendary": 7.0}
    elif char_floor >= 2:
        tier = "silver"
        chest_name = "Серебряный Сундук Катакомб"
        chest_icon = "🥈"
        gold_reward = int((160 + w * 4) * floor_mult) + random.randint(15, 40)
        gems_reward = min(12, 4 + char_floor // 4)
        rarity_weights = {"uncommon": 55.0, "rare": 38.0, "epic": 7.0}
    else:
        tier = "silver"
        chest_name = "Серебряный Сундук Награды"
        chest_icon = "📦"
        gold_reward = int((100 + w * 3) * floor_mult) + random.randint(10, 30)
        gems_reward = 3
        rarity_weights = {"common": 65.0, "uncommon": 33.0, "rare": 2.0}

    # Roll target rarity strictly from this tier's weights
    r_keys = list(rarity_weights.keys())
    r_vals = list(rarity_weights.values())
    target_rarity = random.choices(r_keys, weights=r_vals, k=1)[0]

    pool = [
        it for it in NATAR_ITEMS_CATALOG
        if it.get("rarity") == target_rarity and it.get("slot") in ["weapon", "armor", "relic"]
    ]
    if not pool:
        allowed = [r for r, w_val in rarity_weights.items() if w_val > 0]
        pool = [
            it for it in NATAR_ITEMS_CATALOG
            if it.get("rarity") in allowed and it.get("slot") in ["weapon", "armor", "relic"]
        ]
    if not pool:
        pool = NATAR_ITEMS_CATALOG

    owned_names = set()
    for it in (char.inventory or []):
        if it.get("name"):
            owned_names.add(it["name"].strip().lower())
    for slot, it in (char.equipment or {}).items():
        if isinstance(it, dict) and it.get("name"):
            owned_names.add(it["name"].strip().lower())

    item = pick_smart_loot_item(pool, hero_class=getattr(char, 'hero_class', None), owned_names=owned_names)
    item["uid"] = str(uuid.uuid4())[:8]
    item["upgrade"] = 0
    if "bonus" in item:
        item["bonus"] = dict(item["bonus"])
    rarity = item.get("rarity", target_rarity)
    rarity_data = RARITY_MULTIPLIERS.get(rarity, RARITY_MULTIPLIERS["common"])
    item["rarity_color"] = rarity_data["color"]
    item["rarity_name"] = rarity_data["name"]
    item["bonus_desc"] = rebuild_item_description(item)

    if item.get("type") == "weapon":
        item["min_atk"] = item.get("base_min", 16)
        item["max_atk"] = item.get("base_max", 24)
    elif item.get("type") == "armor":
        item["defense"] = item.get("base_def", 8)
        item["hp_bonus"] = item.get("base_hp", 50)

    char.gold += gold_reward
    char.gems += gems_reward

    inv = list(char.inventory or [])
    if len(inv) < 200:
        inv.append(item)
        char.inventory = inv
        flag_modified(char, "inventory")

    await session.commit()
    await session.refresh(char)

    return {
        "chest_name": chest_name,
        "chest_icon": chest_icon,
        "tier": tier,
        "gold_reward": gold_reward,
        "gems_reward": gems_reward,
        "item": item
    }


async def open_boss_raid_chest(
    session: AsyncSession,
    char: RPGCharacter,
    boss_id: str = "roshan"
) -> Dict[str, Any]:
    """
    Opens an exclusive Raid Boss Treasure Chest!
    Progressive boss loot: early bosses drop Rare/Epic items, high-tier bosses drop Legendaries & Immortals.
    """
    boss_id = str(boss_id or "roshan").strip().lower()

    pool = BOSS_EXCLUSIVE_DROPS.get(boss_id)
    if not pool:
        # If boss has no exclusive drops, open wave chest scaled to boss floor
        boss_floor = BOSS_FLOORS.get(boss_id, getattr(char, "dungeon_floor", 1) or 1)
        return await open_wave_chest(session, char, wave=boss_floor * 20)

    owned_names = set()
    for it in (char.inventory or []):
        if it.get("name"):
            owned_names.add(it["name"].strip().lower())
    for slot, it in (char.equipment or {}).items():
        if isinstance(it, dict) and it.get("name"):
            owned_names.add(it["name"].strip().lower())

    item = pick_smart_loot_item(pool, hero_class=getattr(char, 'hero_class', None), owned_names=owned_names)
    item["uid"] = str(uuid.uuid4())[:8]
    item["upgrade"] = 0
    if "bonus" in item:
        item["bonus"] = dict(item["bonus"])

    rarity = item.get("rarity", "common")
    rarity_data = RARITY_MULTIPLIERS.get(rarity, RARITY_MULTIPLIERS.get("common", {}))
    item["rarity_color"] = rarity_data.get("color", item.get("rarity_color", "#94a3b8"))
    item["rarity_name"] = rarity_data.get("name", item.get("rarity_name", "Обычный"))
    item["bonus_desc"] = rebuild_item_description(item)

    RAID_CHEST_GOLD = {
        "golem": 600, "lich": 1200, "tormentor": 2000, "dragon": 3500,
        "pudge_boss": 5500, "faceless_void": 8500, "roshan": 12000,
        "tidehunter": 16000, "sf_boss": 22000, "necrophos": 30000,
        "terrorblade": 40000, "invoker_boss": 55000, "chaos_knight": 70000,
        "dark_tormentor": 90000, "storm_spirit": 115000, "doom": 145000,
        "primal_beast": 180000, "phantom_roshan": 225000, "tinker_boss": 280000,
        "enigma": 350000
    }
    base_chest_gold = RAID_CHEST_GOLD.get(boss_id, 25000)
    gold_reward = int(base_chest_gold * random.uniform(0.9, 1.15))
    gems_reward = max(5, min(65, int(base_chest_gold / 50000) + 5))

    char.gold += gold_reward
    char.gems += gems_reward

    inv = list(char.inventory or [])
    if len(inv) < 200:
        inv.append(item)
        char.inventory = inv
        flag_modified(char, "inventory")

    await session.commit()
    await session.refresh(char)

    tier = item.get("rarity", "rare")
    chest_icon = "🏆" if tier in ("immortal", "mythic") else ("👑" if tier == "legendary" else "🎁")

    return {
        "chest_name": f"Сокровищница: {item.get('name')}",
        "chest_icon": chest_icon,
        "tier": tier,
        "gold_reward": gold_reward,
        "gems_reward": gems_reward,
        "item": item
    }


