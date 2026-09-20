import math
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from backend.db.models import RPGCharacter

# ==============================================================================
# REBIRTH / ASCENSION MATHEMATICS (Volume IV of GDD)
# ==============================================================================

MAX_REBIRTH_RANK = 40

REBIRTH_RANKS_CONFIG: Dict[int, Dict[str, Any]] = {
    0: {"min_level": 0, "essence_reward": 0, "title": "Смертный Путник"},
    1: {"min_level": 30, "essence_reward": 3, "title": "Пробужденный Воитель"},
    2: {"min_level": 40, "essence_reward": 5, "title": "Вознесшийся Титан"},
    3: {"min_level": 45, "essence_reward": 8, "title": "Повелитель Эфира"},
    4: {"min_level": 50, "essence_reward": 12, "title": "Демиург Бездны"},
    5: {"min_level": 50, "essence_reward": 18, "title": "Звездный Бог Бессмертия"},
    6: {"min_level": 50, "essence_reward": 25, "title": "Архитектор Реальности (VI)"},
    7: {"min_level": 50, "essence_reward": 30, "title": "Архитектор Реальности (VII)"},
    8: {"min_level": 50, "essence_reward": 35, "title": "Архитектор Реальности (VIII)"},
    9: {"min_level": 50, "essence_reward": 40, "title": "Архитектор Реальности (IX)"},
    10: {"min_level": 50, "essence_reward": 50, "title": "Архитектор Реальности (X)"},
    11: {"min_level": 50, "essence_reward": 60, "title": "Владыка Времени (XI)"},
    12: {"min_level": 50, "essence_reward": 75, "title": "Владыка Времени (XII)"},
    13: {"min_level": 50, "essence_reward": 90, "title": "Владыка Времени (XIII)"},
    14: {"min_level": 50, "essence_reward": 110, "title": "Владыка Времени (XIV)"},
    15: {"min_level": 50, "essence_reward": 135, "title": "Галактический Титан (XV)"},
    16: {"min_level": 50, "essence_reward": 165, "title": "Галактический Титан (XVI)"},
    17: {"min_level": 50, "essence_reward": 200, "title": "Галактический Титан (XVII)"},
    18: {"min_level": 50, "essence_reward": 240, "title": "Космический Абсолют (XVIII)"},
    19: {"min_level": 50, "essence_reward": 290, "title": "Космический Абсолют (XIX)"},
    20: {"min_level": 50, "essence_reward": 350, "title": "Повелитель Измерений (XX)"},
    21: {"min_level": 50, "essence_reward": 420, "title": "Повелитель Измерений (XXI)"},
    22: {"min_level": 50, "essence_reward": 500, "title": "Архитектор Сингулярности (XXII)"},
    23: {"min_level": 50, "essence_reward": 600, "title": "Архитектор Сингулярности (XXIII)"},
    24: {"min_level": 50, "essence_reward": 750, "title": "Властелин Вечности (XXIV)"},
    25: {"min_level": 50, "essence_reward": 1000, "title": "Создатель Мультивселенной (XXV)"},
    26: {"min_level": 50, "essence_reward": 1250, "title": "Творец Квантового Эфира (XXVI)"},
    27: {"min_level": 50, "essence_reward": 1550, "title": "Владыка Астральных Сфер (XXVII)"},
    28: {"min_level": 50, "essence_reward": 1900, "title": "Повелитель Темной Материи (XXVIII)"},
    29: {"min_level": 50, "essence_reward": 2350, "title": "Хранитель Изначального Хаоса (XXIX)"},
    30: {"min_level": 50, "essence_reward": 2900, "title": "Бог-Император Пантеона (XXX)"},
    31: {"min_level": 50, "essence_reward": 3600, "title": "Пожиратель Галактик (XXXI)"},
    32: {"min_level": 50, "essence_reward": 4400, "title": "Властелин Черных Дыр (XXXII)"},
    33: {"min_level": 50, "essence_reward": 5400, "title": "Архитектор Космических Нитей (XXXIII)"},
    34: {"min_level": 50, "essence_reward": 6600, "title": "Ткач Пространства и Времени (XXXIV)"},
    35: {"min_level": 50, "essence_reward": 8000, "title": "Абсолютный Демиург Бытия (XXXV)"},
    36: {"min_level": 50, "essence_reward": 9700, "title": "Владыка Высших Измерений (XXXVI)"},
    37: {"min_level": 50, "essence_reward": 11800, "title": "Суверен Нулевой Точки (XXXVII)"},
    38: {"min_level": 50, "essence_reward": 14300, "title": "Повелитель Вечной Сингулярности (XXXVIII)"},
    39: {"min_level": 50, "essence_reward": 17200, "title": "Око Первородной Тьмы (XXXIX)"},
    40: {"min_level": 50, "essence_reward": 21000, "title": "Верховный Бог Мультивселенной (XL)"},
}

CONSTELLATIONS_CATALOG: Dict[str, Dict[str, Any]] = {
    "constellation_vitality": {
        "id": "constellation_vitality",
        "name": "Титаническая Стойкость",
        "icon": "🛡️",
        "desc": "+150 HP и +5 брони за уровень таланта",
        "bonus_per_level": {"hp": 150, "armor": 5},
        "max_level": 10,
        "cost_per_level": 1,
    },
    "constellation_pet": {
        "id": "constellation_pet",
        "name": "Астральная Связь с Питомцем",
        "icon": "🐾",
        "desc": "+20% ко всем характеристикам и урону питомца за ур.",
        "bonus_per_level": {"pet_stat_pct": 20},
        "max_level": 10,
        "cost_per_level": 1,
    },
    "constellation_fortune": {
        "id": "constellation_fortune",
        "name": "Благословение Фортуны",
        "icon": "🍀",
        "desc": "+18% к шансу дропа Mythic и Immortal предметов за ур.",
        "bonus_per_level": {"drop_fortune_pct": 18},
        "max_level": 10,
        "cost_per_level": 1,
    },
    "constellation_boss_pacifier": {
        "id": "constellation_boss_pacifier",
        "name": "Укротитель Ярости Боссов",
        "icon": "⏳",
        "desc": "Замедляет набор стаков Enrage боссов на -14% за ур.",
        "bonus_per_level": {"enrage_slow_pct": 14},
        "max_level": 10,
        "cost_per_level": 1,
    },
    "constellation_brotherhood": {
        "id": "constellation_brotherhood",
        "name": "Узы Боевого Братства",
        "icon": "🤝",
        "desc": "+20% к урону группы в кооперативе за каждого живого союзника",
        "bonus_per_level": {"coop_damage_pct": 20},
        "max_level": 10,
        "cost_per_level": 1,
    },
    "constellation_colossus_slayer": {
        "id": "constellation_colossus_slayer",
        "name": "Палач Колоссов",
        "icon": "⚔️",
        "desc": "+30% чистого урона по боссам с запасом HP > 1 000 000 за ур. (до 30 ур.)",
        "bonus_per_level": {"colossus_damage_pct": 30},
        "max_level": 30,
        "cost_per_level": 1,
    },
}


def calculate_rebirth_multiplier(rank: int) -> float:
    """
    Computes global multiplier to all stats and damage:
    - Ranks 0..10: M(R) = 1 + (R * 0.35) + (R^1.3 * 0.08)  [up to ~6.1x / 9.43x]
    - Ranks 11..25: Exponential 1.31x per rank above 10, smoothly scaling up to ~350x at Rank 25
    """
    if rank <= 0:
        return 1.0
    r = float(rank)
    if rank <= 10:
        mult = 1.0 + (r * 0.35) + (math.pow(r, 1.3) * 0.08)
    else:
        base_10 = 1.0 + (10.0 * 0.35) + (math.pow(10.0, 1.3) * 0.08)
        mult = base_10 * math.pow(1.31, r - 10.0)
    return round(mult, 3)


def get_rebirth_rank_info(rank: int) -> Dict[str, Any]:
    """Returns metadata for the current or specified rebirth rank."""
    cfg = REBIRTH_RANKS_CONFIG.get(rank)
    if not cfg:
        cfg = {"min_level": 50, "essence_reward": 50, "title": f"Архитектор Реальности ({rank})"}
    
    next_rank = rank + 1
    next_cfg = REBIRTH_RANKS_CONFIG.get(next_rank)
    
    return {
        "rank": rank,
        "max_rank": MAX_REBIRTH_RANK,
        "title": cfg["title"],
        "multiplier": calculate_rebirth_multiplier(rank),
        "multiplier_pct": int(round((calculate_rebirth_multiplier(rank) - 1.0) * 100)),
        "next_rank": next_rank if next_rank <= MAX_REBIRTH_RANK else None,
        "next_min_level": next_cfg["min_level"] if next_cfg else None,
        "next_essence_reward": next_cfg["essence_reward"] if next_cfg else None,
    }


async def perform_ascension(session: AsyncSession, char: RPGCharacter) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Performs ascension (rebirth) to the next rank:
    - Resets level to 1 and XP to 0
    - Resets free stat points for grind re-balance
    - ALL inventory, equipment, forge upgrades, pets, gold and gems ARE PRESERVED!
    - Increments rank and awards Astral Essence (✨).
    """
    current_rank = getattr(char, "rebirths", 0)
    if current_rank >= MAX_REBIRTH_RANK:
        return False, f"Достигнут максимальный ранг Вознесения (Ранг {MAX_REBIRTH_RANK} / XL)!", {}

    next_rank = current_rank + 1
    next_cfg = REBIRTH_RANKS_CONFIG.get(next_rank, {"min_level": 50, "essence_reward": 25})
    req_level = next_cfg["min_level"]

    if char.level < req_level:
        return False, f"Для Вознесения на Ранг {next_rank} требуется достичь {req_level} уровня героя (ваш текущий уровень: {char.level})!", {}

    essence_reward = next_cfg["essence_reward"]

    char.level = 1
    char.xp = 0
    char.stat_points = 0
    char.rebirths = next_rank
    char.dungeon_floor = 1
    char.dungeon_cleared = 0

    talents = dict(getattr(char, "talents", {}) or {})
    talents["rebirth_essence"] = talents.get("rebirth_essence", 0) + essence_reward
    char.talents = talents
    flag_modified(char, "talents")

    await session.commit()
    await session.refresh(char)

    mult = calculate_rebirth_multiplier(next_rank)
    title = next_cfg["title"]
    msg = f"🌟 Вознесение завершено! Достигнут Ранг {next_rank} («{title}»). Множитель всех статов: x{mult}. Начислено ✨ +{essence_reward} Астральной Эссенции."
    
    return True, msg, {
        "new_rank": next_rank,
        "title": title,
        "multiplier": mult,
        "essence_awarded": essence_reward,
        "total_essence": talents["rebirth_essence"],
    }


async def upgrade_constellation(
    session: AsyncSession,
    char: RPGCharacter,
    constellation_id: str
) -> Tuple[bool, str, Dict[str, Any]]:
    """Upgrades a constellation node using 1 Astral Essence (✨)."""
    c_cfg = CONSTELLATIONS_CATALOG.get(constellation_id)
    if not c_cfg:
        return False, f"Неизвестное созвездие '{constellation_id}'!", {}

    talents = dict(getattr(char, "talents", {}) or {})
    current_essence = talents.get("rebirth_essence", 0)
    if current_essence < 1:
        return False, "Недостаточно Астральной Эссенции (✨) для прокачки созвездия!", {}

    constellations = dict(talents.get("constellations", {}) or {})
    current_level = constellations.get(constellation_id, 0)
    max_level = c_cfg["max_level"]

    if current_level >= max_level:
        return False, f"Созвездие «{c_cfg['name']}» уже достигло максимального {max_level} уровня!", {}

    new_level = current_level + 1
    constellations[constellation_id] = new_level
    talents["constellations"] = constellations
    talents["rebirth_essence"] = current_essence - 1
    char.talents = talents
    flag_modified(char, "talents")

    await session.commit()
    await session.refresh(char)

    return True, f"✨ Созвездие «{c_cfg['name']}» повышено до {new_level} уровня!", {
        "constellation_id": constellation_id,
        "new_level": new_level,
        "remaining_essence": talents["rebirth_essence"],
    }
