import uuid
import random
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm.attributes import flag_modified

from backend.db.models import RPGCharacter, User
from backend.db.crud.rpg.heroes import NATAR_HEROES
from backend.db.crud.rpg.items_catalog import NATAR_ITEMS_CATALOG, RARITY_MULTIPLIERS
from backend.db.crud.rpg.loot import rebuild_item_description
from backend.db.crud.rpg.progression_math import LEVEL_CAP


from backend.db.crud.rpg.character import get_or_create_rpg_character


DEFAULT_ADMIN_PLAYERS = [
    {"user_id": 1, "tg_id": 7755842535, "name": "Не Вадим", "hero_class": "leshrac", "hero_name": "Мучитель Земли", "hero_icon": "🦌", "level": 28, "gold": 1645000, "gems": 140, "rebirths": 0, "dungeon_floor": 35},
    {"user_id": 5, "tg_id": 1440393642, "name": "Михаил Исайкин", "hero_class": "invoker", "hero_name": "Архимаг Стихий", "hero_icon": "🔮", "level": 43, "gold": 373000, "gems": 4120, "rebirths": 2, "dungeon_floor": 106},
    {"user_id": 24, "tg_id": 6926859962, "name": "Макар", "hero_class": "invoker", "hero_name": "Архимаг Стихий", "hero_icon": "🔮", "level": 35, "gold": 104000, "gems": 760, "rebirths": 0, "dungeon_floor": 16},
    {"user_id": 17, "tg_id": 5181261098, "name": "Глеб", "hero_class": "invoker", "hero_name": "Архимаг Стихий", "hero_icon": "🔮", "level": 21, "gold": 146000, "gems": 1360, "rebirths": 1, "dungeon_floor": 53},
    {"user_id": 4, "tg_id": 1053722876, "name": "notariuspiva", "hero_class": "pudge", "hero_name": "Мясник (Танк)", "hero_icon": "🪝", "level": 18, "gold": 4236000, "gems": 100, "rebirths": 0, "dungeon_floor": 20},
]


async def get_rpg_players_list(session: AsyncSession, limit: int = 100) -> List[Dict[str, Any]]:
    """Returns a list of all users and players with their current RPG stats for the admin panel."""
    stmt = (
        select(User, RPGCharacter)
        .outerjoin(RPGCharacter, RPGCharacter.user_id == User.id)
        .order_by(
            desc(RPGCharacter.level.isnot(None)),
            desc(RPGCharacter.level),
            User.id
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    players = []
    seen_tg_ids = set()
    for user, char in rows:
        seen_tg_ids.add(user.tg_id)
        if char:
            hero_cfg = NATAR_HEROES.get(char.hero_class, {})
            players.append({
                "char_id": char.id,
                "user_id": user.id,
                "tg_id": user.tg_id,
                "name": user.display_name or f"Игрок #{user.id}",
                "username": user.username or "",
                "hero_class": char.hero_class,
                "hero_name": hero_cfg.get("name", char.hero_class),
                "hero_icon": hero_cfg.get("icon", "⚔️"),
                "level": char.level,
                "gold": char.gold,
                "gems": char.gems,
                "rebirths": char.rebirths,
                "dungeon_floor": char.dungeon_floor,
            })
        else:
            players.append({
                "char_id": None,
                "user_id": user.id,
                "tg_id": user.tg_id,
                "name": user.display_name or f"Пользователь #{user.id}",
                "username": user.username or "",
                "hero_class": "newbie",
                "hero_name": "Новичок",
                "hero_icon": "👤",
                "level": 0,
                "gold": 0,
                "gems": 0,
                "rebirths": 0,
                "dungeon_floor": 0,
            })

    if len(players) < 5:
        for p in DEFAULT_ADMIN_PLAYERS:
            if p["tg_id"] not in seen_tg_ids:
                players.append(dict(p))
                seen_tg_ids.add(p["tg_id"])
    return players


async def find_character_and_user(
    session: AsyncSession,
    target: Any
) -> Tuple[Optional[RPGCharacter], Optional[User]]:
    """Locates RPGCharacter and User by User.id, User.tg_id, or RPGCharacter.id."""
    if not target:
        return None, None

    str_target = str(target).strip()
    if not str_target:
        return None, None

    # Try numeric match (user_id, tg_id, char_id)
    if str_target.isdigit():
        num = int(str_target)
        # Check by User.tg_id
        u_res = await session.execute(select(User).where(User.tg_id == num))
        u = u_res.scalars().first()
        if u:
            c = await get_or_create_rpg_character(session, user_id=u.id)
            return c, u

        # Check by User.id
        u_res = await session.execute(select(User).where(User.id == num))
        u = u_res.scalars().first()
        if u:
            c = await get_or_create_rpg_character(session, user_id=u.id)
            return c, u

        # Check by RPGCharacter.id
        c_res = await session.execute(select(RPGCharacter).where(RPGCharacter.id == num))
        c = c_res.scalars().first()
        if c:
            u_res = await session.execute(select(User).where(User.id == c.user_id))
            u = u_res.scalars().first()
            return c, u

        # Auto-create user for test slots or arbitrary IDs on the fly
        new_u = User(tg_id=num, full_name=f"Игрок #{num}", role="student")
        session.add(new_u)
        await session.flush()
        c = await get_or_create_rpg_character(session, user_id=new_u.id)
        return c, new_u

    # Try username or display name match
    clean_uname = str_target.lstrip("@").lower()
    u_res = await session.execute(
        select(User).where(
            User.username.ilike(clean_uname)
            | User.full_name.ilike(str_target)
            | User.custom_name.ilike(str_target)
        )
    )
    u = u_res.scalars().first()
    if u:
        c = await get_or_create_rpg_character(session, user_id=u.id)
        return c, u

    new_u = User(tg_id=random.randint(900000000, 999999999), username=clean_uname, full_name=f"@{clean_uname}", role="student")
    session.add(new_u)
    await session.flush()
    c = await get_or_create_rpg_character(session, user_id=new_u.id)
    return c, new_u


async def admin_give_gold(
    session: AsyncSession,
    char: RPGCharacter,
    amount: int
) -> Tuple[bool, str, int]:
    """Awards or deducts gold for a character."""
    char.gold = max(0, int(char.gold + amount))
    await session.commit()
    await session.refresh(char)
    return True, f"Баланс золота изменен на {'+' if amount >= 0 else ''}{amount} 🪙. Новый баланс: {char.gold} 🪙", char.gold


async def admin_give_gems(
    session: AsyncSession,
    char: RPGCharacter,
    amount: int
) -> Tuple[bool, str, int]:
    """Awards or deducts gems (crystals) for a character."""
    char.gems = max(0, int(char.gems + amount))
    await session.commit()
    await session.refresh(char)
    return True, f"Баланс кристаллов изменен на {'+' if amount >= 0 else ''}{amount} 💎. Новый баланс: {char.gems} 💎", char.gems


async def admin_set_character_level(
    session: AsyncSession,
    char: RPGCharacter,
    new_level: int
) -> Tuple[bool, str, int]:
    """Sets character level (1..50) and recalculates base stats and skill points accordingly."""
    lvl = max(1, min(LEVEL_CAP, int(new_level)))
    hero_cfg = NATAR_HEROES.get(char.hero_class, NATAR_HEROES.get("pudge", {}))

    base_str = hero_cfg.get("str", 20)
    base_agi = hero_cfg.get("agi", 15)
    base_int = hero_cfg.get("int", 15)
    str_gain = hero_cfg.get("str_gain", 2.5)
    agi_gain = hero_cfg.get("agi_gain", 2.0)
    int_gain = hero_cfg.get("int_gain", 2.0)

    char.level = lvl
    char.xp = 0
    char.strength = int(base_str + (lvl - 1) * str_gain)
    char.agility = int(base_agi + (lvl - 1) * agi_gain)
    char.intelligence = int(base_int + (lvl - 1) * int_gain)
    char.vitality = 10 + (lvl - 1)
    char.stat_points = (lvl - 1) * 2
    char.talent_points = lvl // 2

    await session.commit()
    await session.refresh(char)
    return True, f"Уровень героя установлен на {lvl} (Сила: {char.strength}, Ловкость: {char.agility}, Интеллект: {char.intelligence}, Очков талантов: {char.talent_points})", lvl


async def admin_give_custom_item(
    session: AsyncSession,
    char: RPGCharacter,
    rarity: str = "legendary",
    item_level: int = 1,
    item_name: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """Creates a custom item with specific rarity and level and places it into inventory."""
    rarity = str(rarity).lower().strip()
    if rarity not in RARITY_MULTIPLIERS:
        rarity = "legendary"

    rarity_data = RARITY_MULTIPLIERS[rarity]
    item_level = max(1, min(50, int(item_level)))

    # Find item template
    template = None
    if item_name:
        clean_name = item_name.strip().lower()
        for it in NATAR_ITEMS_CATALOG:
            if clean_name in it.get("name", "").lower():
                template = dict(it)
                break

    if not template:
        # Match by rarity or pick random
        matching = [it for it in NATAR_ITEMS_CATALOG if it.get("rarity") == rarity]
        pool = matching if matching else NATAR_ITEMS_CATALOG
        template = dict(random.choice(pool))

    # Construct custom item
    new_item = dict(template)
    new_item["uid"] = str(uuid.uuid4())[:8]
    new_item["rarity"] = rarity
    new_item["rarity_name"] = rarity_data["name"]
    new_item["rarity_color"] = rarity_data["color"]
    new_item["floor"] = item_level
    new_item["upgrade"] = 0

    if "bonus" in new_item:
        new_item["bonus"] = dict(new_item["bonus"])

    # Scale stats by level and rarity multiplier
    scale = (1.0 + (item_level * 0.12)) * rarity_data["mult"]
    if new_item.get("type") == "weapon":
        new_item["min_atk"] = max(10, int(new_item.get("base_min", 20) * scale))
        new_item["max_atk"] = max(new_item["min_atk"] + 6, int(new_item.get("base_max", 30) * scale))
    elif new_item.get("type") == "armor":
        new_item["defense"] = max(5, int(new_item.get("base_def", 10) * scale))
        new_item["hp_bonus"] = max(30, int(new_item.get("base_hp", 60) * scale))
    elif new_item.get("type") == "potion":
        new_item["heal_hp"] = max(100, int(150 * scale))
        new_item["heal_mp"] = max(50, int(75 * scale))

    new_item["bonus_desc"] = rebuild_item_description(new_item)

    inv = list(char.inventory or [])
    inv.append(new_item)
    char.inventory = inv
    flag_modified(char, "inventory")

    await session.commit()
    await session.refresh(char)
    return True, f"Выдан предмет «{new_item.get('name')}» [{rarity_data['name']}, Ур. {item_level}]!", new_item


async def admin_full_reset_player(
    session: AsyncSession,
    char: RPGCharacter
) -> Tuple[bool, str]:
    """Completely resets an arbitrary player's RPG character to level 1 baseline."""
    h_class = char.hero_class or "pudge"
    config = NATAR_HEROES.get(h_class, NATAR_HEROES.get("pudge", {}))

    char.level = 1
    char.xp = 0
    char.gold = 150
    char.gems = 10
    char.stat_points = 2
    char.talent_points = 0
    char.strength = config.get("str", 25)
    char.agility = config.get("agi", 14)
    char.intelligence = config.get("int", 16)
    char.vitality = 10
    char.rebirths = 0
    char.talents = {}
    char.dungeon_floor = 1
    char.dungeon_cleared = 0
    char.boss_kills = 0
    char.pvp_rating = 1000
    char.pvp_wins = 0
    char.pvp_losses = 0
    char.pets = []

    starter_w = dict(config.get("starter_weapon", {}))
    starter_a = dict(config.get("starter_armor", {}))
    starter_w["uid"] = str(uuid.uuid4())[:8]
    starter_a["uid"] = str(uuid.uuid4())[:8]
    starter_w["slot"] = "slot_1"
    starter_a["slot"] = "slot_5"

    char.equipment = {
        "slot_1": starter_w,
        "slot_5": starter_a,
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
    flag_modified(char, "talents")

    await session.commit()
    await session.refresh(char)
    return True, "Прогресс игрока успешно полностью обнулен (1 уровень, стартовая экипировка)."
