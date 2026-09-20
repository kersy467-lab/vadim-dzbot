import math
from typing import Dict, Any, List

LEVEL_CAP = 50
STAT_POINTS_PER_LEVEL = 5

PROGRESSION_MILESTONES: Dict[int, Dict[str, Any]] = {
    1: {"name": "Базовые навыки", "desc": "Базовая атака и Скилл 1"},
    5: {"name": "Спутник", "desc": "Разблокировка слота питомца, Скилл 2"},
    10: {"name": "Кузница", "desc": "Разблокировка Кузницы заточки, Скилл 3"},
    15: {"name": "Реликвии и Талант", "desc": "Талант 10 ур. Dota 2, Слот реликвий"},
    20: {"name": "ULTIMATE", "desc": "Разблокировка ультимейта героя, Талант 15 ур."},
    25: {"name": "Героические Рейды", "desc": "Доступ к героическим рейдовым боссам"},
    30: {"name": "Вознесение I", "desc": "Доступ к 1-му Перерождению (Ранг I)"},
    35: {"name": "Мифические Рейды", "desc": "Талант 20 ур., доступ к мифическим рейдам"},
    40: {"name": "Вознесение II", "desc": "Доступ ко 2-му Перерождению (Ранг II)"},
    45: {"name": "Вознесение III", "desc": "Доступ к 3-му Перерождению (Ранг III)"},
    50: {"name": "Абсолютный Кап", "desc": "Перерождения IV и V, Рейд Nightmare"},
}


def calculate_xp_for_level(level: int) -> int:
    """
    Computes required XP to advance from current level to next:
    XP_req(L) = floor(100 * L^1.85 + 50 * L)
    """
    if level < 1:
        return 150
    return int(math.floor(100.0 * (float(level) ** 1.85) + 50.0 * float(level)))


def get_unlocked_features(level: int) -> Dict[str, bool]:
    """Returns dictionary of unlocked features for the given character level."""
    return {
        "skill_1": True,
        "skill_2": level >= 5,
        "skill_3": level >= 10,
        "ultimate": level >= 20,
        "pets": level >= 5,
        "forge": level >= 10,
        "relics": level >= 15,
        "talent_10": level >= 15,
        "talent_15": level >= 20,
        "talent_20": level >= 35,
        "talent_25": level >= 50,
        "heroic_raids": level >= 25,
        "mythic_raids": level >= 35,
        "nightmare_raids": level >= 50,
        "rebirth_rank_1": level >= 30,
        "rebirth_rank_2": level >= 40,
        "rebirth_rank_3": level >= 45,
        "rebirth_rank_4": level >= 50,
    }


def calculate_base_attribute_stats(
    strength: int,
    agility: int,
    intelligence: int,
    primary_attr: str = "Сила"
) -> Dict[str, Any]:
    """
    Calculates base character attributes strictly following Volume III of GDD:
    - STR: HP = 150 + (STR * 24), HP Regen = 0.5 + (STR * 0.08)/s
    - AGI: Armor = floor(AGI * 0.18), Crit = 5% + (AGI * 0.12)%, Speed = 100% + (AGI * 0.05)%
    - INT: MP = 100 + (INT * 16), MP Regen = 1.0 + (INT * 0.10)/s, Spell Power = 1.0 + (INT * 0.015)
    - Primary Attr: Base Attack = PrimaryAttr * 1.8
    """
    s_val = max(1, int(strength))
    a_val = max(1, int(agility))
    i_val = max(1, int(intelligence))

    p_norm = (primary_attr or "Сила").strip().lower()
    if "ловк" in p_norm or "agi" in p_norm:
        base_atk = round(a_val * 1.8, 1)
    elif "инт" in p_norm or "int" in p_norm:
        base_atk = round(i_val * 1.8, 1)
    else:
        base_atk = round(s_val * 1.8, 1)

    hp = int(150 + (s_val * 24))
    hp_regen = round(0.5 + (s_val * 0.08), 2)

    armor = int(math.floor(a_val * 0.18))
    crit_chance = round(5.0 + (a_val * 0.12), 2)
    move_speed_pct = round(100.0 + (a_val * 0.05), 2)

    mp = int(100 + (i_val * 16))
    mp_regen = round(1.0 + (i_val * 0.10), 2)
    spell_power = round(1.0 + (i_val * 0.015), 3)

    return {
        "hp": hp,
        "hp_regen": hp_regen,
        "mp": mp,
        "mp_regen": mp_regen,
        "armor": armor,
        "crit_chance": crit_chance,
        "move_speed_pct": move_speed_pct,
        "spell_power": spell_power,
        "base_atk": base_atk,
    }


def get_full_progression_table() -> List[Dict[str, Any]]:
    """Builds complete table for levels 1 to 50 with XP and unlocks."""
    table = []
    cumulative_xp = 0
    for lvl in range(1, LEVEL_CAP + 1):
        xp_needed = calculate_xp_for_level(lvl) if lvl < LEVEL_CAP else 0
        milestone = PROGRESSION_MILESTONES.get(lvl)
        stat_points_total = (lvl - 1) * STAT_POINTS_PER_LEVEL
        table.append({
            "level": lvl,
            "xp_required": xp_needed,
            "cumulative_xp": cumulative_xp,
            "stat_points_total": stat_points_total,
            "milestone": milestone["name"] if milestone else None,
            "description": milestone["desc"] if milestone else None,
            "unlocked_features": get_unlocked_features(lvl),
        })
        cumulative_xp += xp_needed
    return table
