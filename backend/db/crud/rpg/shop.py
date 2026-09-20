import random
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from backend.db.models import RPGCharacter, User
from backend.db.crud.rpg.items_catalog import NATAR_ITEMS_CATALOG, RARITY_MULTIPLIERS
from backend.db.crud.rpg.shop_catalog import NATAR_SHOP_CATALOG
from backend.db.crud.rpg.loot import rebuild_item_description, generate_random_natar_item
from backend.db.crud.rpg.character import (
    get_or_create_rpg_character,
    serialize_character_profile,
    calculate_character_effective_stats,
)
from backend.db.crud.rpg.heroes import NATAR_HEROES
from backend.db.crud.rpg.progression_math import (
    calculate_xp_for_level,
    LEVEL_CAP,
    STAT_POINTS_PER_LEVEL
)

# ==============================================================================
# NATARGRP SHOP (ТАЙНАЯ ЛАВКА СНАРЯЖЕНИЯ)
# ==============================================================================

# ==============================================================================
# NATARGRP SHOP (ТАЙНАЯ ЛАВКА СНАРЯЖЕНИЯ)
# ==============================================================================

def get_rpg_shop_catalog() -> List[Dict[str, Any]]:
    """Returns list of items available in the Secret Shop."""
    return list(NATAR_SHOP_CATALOG)


async def buy_item_from_shop(
    session: AsyncSession,
    char: RPGCharacter,
    item_id: str
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Buys an item or consumable from the Shop."""
    inventory = list(char.inventory or [])
    if len(inventory) >= 200:
        return False, "Инвентарь полон (максимум 200 слотов). Освободите место перед покупкой!", None

    shop_item = next((it for it in NATAR_SHOP_CATALOG if it["id"] == item_id), None)
    if not shop_item:
        return False, "Товар не найден в лавке.", None

    cost_gold = shop_item.get("price_gold", 0)
    cost_gems = shop_item.get("price_gems", 0)

    if char.gold < cost_gold:
        return False, f"Недостаточно золота! Нужно {cost_gold} 🪙 (у вас {char.gold} 🪙).", None
    if char.gems < cost_gems:
        return False, f"Недостаточно самоцветов! Нужно {cost_gems} 💎 (у вас {char.gems} 💎).", None

    char.gold -= cost_gold
    char.gems -= cost_gems

    new_item = dict(shop_item)
    new_item["uid"] = str(uuid.uuid4())[:8]
    new_item["upgrade"] = 0
    if "bonus" in shop_item:
        new_item["bonus"] = dict(shop_item["bonus"])

    rarity = new_item.get("rarity", "common")
    rarity_data = RARITY_MULTIPLIERS.get(rarity, RARITY_MULTIPLIERS["common"])
    new_item["rarity_color"] = rarity_data["color"]
    new_item["rarity_name"] = rarity_data["name"]
    new_item["bonus_desc"] = rebuild_item_description(new_item)

    if new_item.get("type") == "weapon":
        new_item["min_atk"] = new_item.get("base_min", 16)
        new_item["max_atk"] = new_item.get("base_max", 24)
    elif new_item.get("type") == "armor":
        new_item["defense"] = new_item.get("base_def", 10)
        new_item["hp_bonus"] = new_item.get("base_hp", 40)

    inventory.append(new_item)
    char.inventory = inventory
    flag_modified(char, "inventory")

    await session.commit()
    await session.refresh(char)
    return True, f"Куплено «{new_item['name']}» за {cost_gold} 🪙!", new_item


async def upgrade_character_base_stat(
    session: AsyncSession,
    char: RPGCharacter,
    stat_name: str,
    amount: Any = 1
) -> Tuple[bool, str]:
    """
    Upgrades Strength, Agility or Intelligence by 1, 10, 100 or 'max'.
    Priority: Spends free level-up stat_points first. If none, spends farmed gold.
    """
    STAT_ALIAS = {
        "str": "strength",
        "strength": "strength",
        "сила": "strength",
        "agi": "agility",
        "agility": "agility",
        "ловкость": "agility",
        "int": "intelligence",
        "intelligence": "intelligence",
        "интеллект": "intelligence",
        "vit": "strength",
        "vitality": "strength"
    }
    actual_stat = STAT_ALIAS.get(stat_name.strip().lower())
    if not actual_stat:
        return False, "Неверная характеристика. Выберите: Сила, Ловкость или Интеллект."

    target_count = 1
    is_max = False
    str_amt = str(amount).strip().lower()
    if str_amt in ("max", "макс", "all", "все"):
        is_max = True
    else:
        try:
            target_count = max(1, int(amount))
        except (ValueError, TypeError):
            target_count = 1

    current_val = getattr(char, actual_stat, 10)
    stat_points = getattr(char, "stat_points", 0)

    upgraded = 0
    points_used = 0
    gold_spent = 0
    limit = 10000 if is_max else target_count

    while upgraded < limit:
        if stat_points > 0:
            stat_points -= 1
            points_used += 1
            upgraded += 1
            current_val += 1
        else:
            cost = int((current_val ** 1.35) * 6)
            if char.gold >= cost:
                char.gold -= cost
                gold_spent += cost
                upgraded += 1
                current_val += 1
            else:
                break

    stat_ru = {"strength": "Сила", "agility": "Ловкость", "intelligence": "Интеллект"}
    ru_name = stat_ru.get(actual_stat, actual_stat)

    if upgraded == 0:
        cost = int((current_val ** 1.35) * 6)
        return False, f"Недостаточно золота для прокачки {ru_name}! Нужно {cost:,} 🪙 (у вас {char.gold:,} 🪙) или очки характеристик."

    char.stat_points = stat_points
    setattr(char, actual_stat, current_val)
    if actual_stat == "strength":
        char.vitality = char.strength

    await session.commit()
    await session.refresh(char)

    parts = []
    if points_used > 0:
        parts.append(f"потрачено очков: {points_used}")
    if gold_spent > 0:
        parts.append(f"золота: {gold_spent:,} 🪙")
    cost_str = f" ({', '.join(parts)})" if parts else ""

    return True, f"Характеристика {ru_name} успешно повышена на +{upgraded} (теперь {current_val}){cost_str}!"


async def add_xp_and_gold_to_character(
    session: AsyncSession,
    char: RPGCharacter,
    xp_amount: int,
    gold_amount: int
) -> Tuple[bool, int]:
    """Awards gold, XP and handles Level-ups (+1 free stat point per level, steeper XP curve)."""
    from backend.db.crud.rpg.character import calculate_character_effective_stats
    stats = calculate_character_effective_stats(char)
    pet_gold_mult = stats.get("pet_gold_mult", 1.0)
    pet_xp_mult = stats.get("pet_xp_mult", 1.0)

    char.gold += int(gold_amount * pet_gold_mult)
    char.xp += int(xp_amount * pet_xp_mult)
    leveled_up = False

    while True:
        if char.level >= LEVEL_CAP:
            needed = calculate_xp_for_level(LEVEL_CAP)
            char.xp = min(char.xp, needed)
            break
        needed = calculate_xp_for_level(char.level)
        if char.xp >= needed:
            char.xp -= needed
            char.level += 1
            char.stat_points = getattr(char, "stat_points", 0) + STAT_POINTS_PER_LEVEL
            char.gems += 2
            if char.level % 2 == 0:
                char.talent_points = getattr(char, "talent_points", 0) + 1
            
            # PET SYSTEM: Apply Gold & XP Multipliers
            pet_gold_mult = 1.0
            pet_xp_mult = 1.0
            pets = getattr(char, "pets", []) or []
            for p in pets:
                if p.get("is_equipped"):
                    pet_gold_mult *= p.get("gold_mult", 1.0)
                    pet_xp_mult *= p.get("xp_mult", 1.0)

            # Apply automatic stat gains
            hero_cfg = NATAR_HEROES.get(char.hero_class, NATAR_HEROES.get("pudge", {}))
            char.strength = int(char.strength + hero_cfg.get("str_gain", 2.0))
            char.agility = int(char.agility + hero_cfg.get("agi_gain", 2.0))
            char.intelligence = int(char.intelligence + hero_cfg.get("int_gain", 2.0))
            
            leveled_up = True
        else:
            break

    await session.commit()
    await session.refresh(char)
    return leveled_up, char.level


# ==============================================================================
# LEADERBOARD
# ==============================================================================

async def get_rpg_leaderboard_data(session: AsyncSession) -> List[Dict[str, Any]]:
    """Returns class leaderboard ranked by PvP rating, dungeon floor and gear score."""
    stmt = (
        select(RPGCharacter, User)
        .join(User, RPGCharacter.user_id == User.id)
        .order_by(desc(RPGCharacter.pvp_rating), desc(RPGCharacter.level), desc(RPGCharacter.dungeon_floor))
        .limit(30)
    )
    res = await session.execute(stmt)
    rows = res.all()

    leaderboard = []
    for rank, (char, user) in enumerate(rows, 1):
        stats = calculate_character_effective_stats(char)
        cfg = NATAR_HEROES.get(char.hero_class, NATAR_HEROES["pudge"])
        leaderboard.append({
            "rank": rank,
            "user_id": user.id,
            "tg_id": user.tg_id,
            "name": user.display_name,
            "hero_class": char.hero_class,
            "class_name": cfg["name"],
            "class_icon": cfg["icon"],
            "class_avatar": cfg.get("avatar", "🗡️"),
            "level": char.level,
            "gear_score": stats["gear_score"],
            "pvp_rating": char.pvp_rating,
            "pvp_wins": char.pvp_wins,
            "dungeon_floor": char.dungeon_floor,
            "boss_kills": char.boss_kills
        })
    return leaderboard
