import random
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from backend.db.models import RPGCharacter
from backend.db.crud.rpg.loot import rebuild_item_description
from backend.db.crud.rpg.items_catalog import RARITY_MULTIPLIERS
from backend.db.crud.rpg.character import get_or_create_rpg_character, serialize_character_profile
from backend.db.crud.rpg.heroes import NATAR_HEROES

def calculate_item_sell_price(item: Dict[str, Any], char_floor: int = 1) -> int:
    """Calculates balanced gold value for selling an item based on rarity, floor and upgrades."""
    rarity = item.get("rarity", "common")
    base_price = RARITY_MULTIPLIERS.get(rarity, {}).get("sell", 40)
    item_floor = max(1, item.get("floor") or char_floor)
    floor_multiplier = 1.0 + min(20, item_floor - 1) * 0.05
    upgrade_bonus = min(item.get("upgrade", 0), 15) * 40
    return int(base_price * 0.5 * floor_multiplier) + upgrade_bonus


async def sell_item_from_inventory(
    session: AsyncSession,
    char: RPGCharacter,
    item_uid: str
) -> Tuple[bool, str, int]:
    """Sells an inventory or equipped item for gold."""
    inventory = list(char.inventory or [])
    target_idx = None
    for idx, it in enumerate(inventory):
        if it.get("uid") == item_uid or it.get("id") == item_uid:
            target_idx = idx
            break

    char_floor = getattr(char, "dungeon_floor", 1) or 1
    if target_idx is not None:
        item = inventory.pop(target_idx)
        price = calculate_item_sell_price(item, char_floor)

        char.gold += price
        char.inventory = inventory
        flag_modified(char, "inventory")
        await session.commit()
        await session.refresh(char)
        return True, f"Продано «{item['name']}» за +{price} 🪙", price

    # Check equipment slots if item is currently equipped
    equipment = dict(char.equipment or {})
    target_slot = None
    equipped_item = None
    for slot_k, eq_it in equipment.items():
        if eq_it and (eq_it.get("uid") == item_uid or eq_it.get("id") == item_uid):
            target_slot = slot_k
            equipped_item = eq_it
            break

    if target_slot is not None and equipped_item:
        price = calculate_item_sell_price(equipped_item, char_floor)

        del equipment[target_slot]
        char.equipment = equipment
        char.gold += price
        flag_modified(char, "equipment")
        await session.commit()
        await session.refresh(char)
        return True, f"Снято и продано «{equipped_item['name']}» за +{price} 🪙", price

    return False, "Предмет не найден в инвентаре или снаряжении.", 0


async def sell_multiple_items_from_inventory(
    session: AsyncSession,
    char: RPGCharacter,
    item_uids: list
) -> tuple[bool, str, int, int]:
    """Sells multiple items from inventory or equipment in a single atomic transaction."""
    if not item_uids:
        return False, "Не выбрано ни одного предмета для продажи.", 0, 0

    uid_set = set(str(u) for u in item_uids)
    inventory = list(char.inventory or [])
    equipment = dict(char.equipment or {})
    sold_items = []
    remaining_inv = []
    total_gold = 0

    char_floor = getattr(char, "dungeon_floor", 1) or 1
    for it in inventory:
        it_uid = str(it.get("uid") or it.get("id") or "")
        if it_uid in uid_set:
            price = calculate_item_sell_price(it, char_floor)
            total_gold += price
            sold_items.append(it)
        else:
            remaining_inv.append(it)

    eq_modified = False
    for slot_k, eq_it in list(equipment.items()):
        if eq_it:
            it_uid = str(eq_it.get("uid") or eq_it.get("id") or "")
            if it_uid in uid_set:
                price = calculate_item_sell_price(eq_it, char_floor)
                total_gold += price
                sold_items.append(eq_it)
                del equipment[slot_k]
                eq_modified = True

    if not sold_items:
        return False, "Выбранные предметы не найдены в инвентаре или снаряжении.", 0, 0

    char.gold += total_gold
    char.inventory = remaining_inv
    flag_modified(char, "inventory")
    if eq_modified:
        char.equipment = equipment
        flag_modified(char, "equipment")
    await session.commit()
    await session.refresh(char)

    return True, f"Продано {len(sold_items)} предметов за +{total_gold} 🪙!", total_gold, len(sold_items)


async def reset_rpg_character(
    session: AsyncSession,
    char: RPGCharacter
) -> tuple[bool, str]:
    """Hardcore Reset: Resets RPG character back to level 1 for a fresh grind!"""
    h_class = char.hero_class or "pudge"
    config = NATAR_HEROES.get(h_class, NATAR_HEROES["pudge"])

    char.level = 1
    char.xp = 0
    char.gold = 50
    char.gems = 5
    char.stat_points = 0
    char.strength = config["str"]
    char.agility = config["agi"]
    char.intelligence = config["int"]
    char.vitality = 10
    char.dungeon_floor = 1
    char.dungeon_cleared = 0
    char.boss_kills = 0

    starter_weapon = dict(config["starter_weapon"])
    starter_armor = dict(config["starter_armor"])
    starter_weapon["uid"] = str(uuid.uuid4())[:8]
    starter_armor["uid"] = str(uuid.uuid4())[:8]

    starter_weapon["slot"] = "slot_1"
    starter_armor["slot"] = "slot_5"

    char.equipment = {
        "slot_1": starter_weapon,
        "slot_5": starter_armor,
    }
    char.inventory = [
        {
            "uid": str(uuid.uuid4())[:8],
            "name": "Зелье Исцеления",
            "icon": "🧪",
            "type": "potion",
            "slot": "consumable",
            "slot_name": "Зелье",
            "slot_icon": "🧪",
            "rarity": "common",
            "rarity_name": "Обычный",
            "rarity_color": "#94a3b8",
            "heal_hp": 120,
            "heal_mp": 30,
            "count": 2,
            "bonus_desc": "❤️ Восстанавливает 120 HP и 30 MP (2 шт.)"
        }
    ]
    flag_modified(char, "equipment")
    flag_modified(char, "inventory")
    await session.commit()
    await session.refresh(char)
    return True, "Герой успешно сброшен до 1 уровня! Начинается хардкорное приключение!"


