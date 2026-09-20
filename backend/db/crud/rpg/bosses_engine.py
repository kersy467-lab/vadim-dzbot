"""
natarGRP Bosses Engine — Dynamic scaling, Enrage timer, Phases, and Telegraph attacks.
Conforms to Specification 3.0.0-ULTIMATE (Volume VII).
"""
import math
from typing import Dict, Any, List, Optional

# 7.1. Множители сложности (M_difficulty)
BOSS_DIFFICULTIES: Dict[str, Dict[str, Any]] = {
    "normal": {
        "id": "normal",
        "name": "Обычный (Normal)",
        "hp_mult": 1.0,
        "atk_mult": 1.0,
        "reward_mult": 1.0,
        "mythic_drop_pct": 2.0,
        "immortal_drop_pct": 0.0,
    },
    "heroic": {
        "id": "heroic",
        "name": "Героический (Heroic)",
        "hp_mult": 2.6,
        "atk_mult": 1.8,
        "reward_mult": 2.8,
        "mythic_drop_pct": 8.0,
        "immortal_drop_pct": 0.0,
    },
    "mythic": {
        "id": "mythic",
        "name": "Мифический (Mythic)",
        "hp_mult": 6.5,
        "atk_mult": 3.2,
        "reward_mult": 7.0,
        "mythic_drop_pct": 25.0,
        "immortal_drop_pct": 6.0,
    },
    "nightmare": {
        "id": "nightmare",
        "name": "Кошмар (Nightmare)",
        "hp_mult": 16.0,
        "atk_mult": 5.8,
        "reward_mult": 18.0,
        "mythic_drop_pct": 65.0,
        "immortal_drop_pct": 22.0,
    },
}

# 7.2. Ростер рейдовых боссов Dota 2 с телеграфными атаками
DOTA_BOSS_CATALOG: Dict[str, Dict[str, Any]] = {
    "roshan": {
        "id": "roshan",
        "name": "Бессмертный Рошан",
        "title": "Immortal Roshan",
        "icon": "👹",
        "base_hp": 2_800_000,
        "base_atk": 850,
        "base_atk_max": 1200,
        "defense": 140,
        "gold_reward": 35000,
        "gems_reward": 250,
        "guaranteed_drop": ["legendary", "mythic"],
        "special_drop": "Aegis of the Immortal",
        "desc": "Владыка Логова Рошана. Обладает защитой от заклинаний, сокрушительным хлопком Slam и огненным дыханием.",
        "telegraph_attacks": [
            {
                "id": "slam",
                "name": "Slam (Хлопок о землю)",
                "type": "circle",
                "radius": 280,
                "telegraph_time": 1.8,
                "damage": 1800,
                "effect": "slow",
                "slow_pct": 60,
                "duration": 3.0,
                "description": "Красный телеграф-круг R=280px (1.8с). Наносит 1800 урона и замедляет на -60%."
            },
            {
                "id": "fire_breath",
                "name": "Fire Breath (Огненное Дыхание)",
                "type": "cone",
                "range": 500,
                "angle_deg": 60,
                "telegraph_time": 1.5,
                "damage": 1400,
                "description": "Огненный конус через арену с колоссальным уроном."
            },
            {
                "id": "spellblock",
                "name": "Spellblock (Линка)",
                "type": "passive",
                "cooldown": 12.0,
                "description": "Каждые 12 секунд блокирует одно направленное заклинание героя."
            }
        ]
    },
    "tormentor": {
        "id": "tormentor",
        "name": "Древний Терзатель",
        "title": "Ancient Tormentor",
        "icon": "🔮",
        "base_hp": 1_200_000,
        "base_atk": 450,
        "base_atk_max": 650,
        "defense": 90,
        "gold_reward": 20000,
        "gems_reward": 150,
        "guaranteed_drop": ["legendary"],
        "special_drop": "Aghanim's Shard",
        "desc": "Древний конструкт с зеркальным отражением урона и психо-барьером.",
        "telegraph_attacks": [
            {
                "id": "mirror_reflection",
                "name": "Mirror Reflection (Зеркальное Отражение)",
                "type": "passive_reflect",
                "reflect_pct": 35,
                "description": "Отражает 35% всего полученного урона во случайного игрока рейда."
            },
            {
                "id": "psionic_barrier",
                "name": "Psionic Barrier (Псионический Барьер)",
                "type": "shield",
                "shield_amount": 300000,
                "trigger_interval_pct": 25,
                "description": "Каждые 25% потерянного HP активирует щит на 300 000 прочности."
            }
        ]
    },
    "primal_beast": {
        "id": "primal_beast",
        "name": "Первобытный Зверь",
        "title": "Primal Beast",
        "icon": "🦣",
        "base_hp": 3_500_000,
        "base_atk": 900,
        "base_atk_max": 1350,
        "defense": 120,
        "gold_reward": 40000,
        "gems_reward": 280,
        "guaranteed_drop": ["mythic"],
        "special_drop": "Titan Blood Fragment",
        "desc": "Яростное первобытное чудовище. Проносится через арену сметая всё на пути.",
        "telegraph_attacks": [
            {
                "id": "onslaught",
                "name": "Onslaught (Разбег)",
                "type": "line_charge",
                "width": 120,
                "telegraph_time": 3.0,
                "damage": 3500,
                "description": "Красная полоса разбега через весь экран (3.0с). Наносит 3500 урона!"
            },
            {
                "id": "trample",
                "name": "Trample (Камнепад)",
                "type": "aoe_falling_rocks",
                "telegraph_time": 1.2,
                "damage": 1200,
                "description": "Топает по арене, обрушивая астероиды с потолка."
            }
        ]
    },
    "archlich": {
        "id": "archlich",
        "name": "Архилич Кел'Тузад",
        "title": "Archlich Kel'Thuzad",
        "icon": "☠️",
        "base_hp": 2_000_000,
        "base_atk": 750,
        "base_atk_max": 1100,
        "defense": 80,
        "gold_reward": 30000,
        "gems_reward": 200,
        "guaranteed_drop": ["legendary", "mythic"],
        "special_drop": "Orb of Frostbite",
        "desc": "Владыка темной магии льда. Запускает смертоносный Chain Frost между целями.",
        "telegraph_attacks": [
            {
                "id": "chain_frost",
                "name": "Chain Frost (Чайник Лича)",
                "type": "bouncing_orb",
                "max_bounces": 10,
                "base_damage": 1500,
                "bounce_dmg_growth_pct": 20,
                "description": "Ледяной шар отскакивает до 10 раз, с каждым отскоком усиливая урон на +20%!"
            }
        ]
    }
}


def calculate_enrage_multiplier(elapsed_seconds: float, pacifier_level: int = 0) -> float:
    """
    Volume VII, 7.1: Enrage Timer:
    Каждые 8 секунд затянувшегося боя босс получает +1 стак Enrage (+14% урона):
    M_enrage(t) = 1 + (floor(t / 8) * 0.14)
    Созвездие Укротителя (constellation_boss_pacifier) снижает скорость набора стаков
    на 14% за уровень.
    """
    if elapsed_seconds <= 0:
        return 1.0

    raw_stacks = int(elapsed_seconds // 8)
    slow_pct = min(100.0, max(0.0, float(pacifier_level) * 14.0))
    stack_multiplier = max(0.0, 1.0 - (slow_pct / 100.0))
    effective_stacks = raw_stacks * stack_multiplier

    return round(1.0 + (effective_stacks * 0.14), 4)


def get_boss_phase_state(current_hp: int, max_hp: int) -> Dict[str, Any]:
    """
    Volume VII, 7.1: Phase Transitions:
    - Фаза 1 (100% - 70% HP): M_phase = 1.0
    - Фаза 2 (70% - 30% HP): M_phase = 1.25, elemental shield 25%, spawns adds
    - Фаза 3 (<30% HP): M_phase = 1.55, +50% attack speed, fire trails
    """
    if max_hp <= 0:
        hp_pct = 1.0
    else:
        hp_pct = max(0.0, min(1.0, current_hp / max_hp))

    if hp_pct > 0.70:
        return {
            "phase": 1,
            "name": "Фаза 1: Базовый натиск",
            "phase_mult": 1.0,
            "shield_pct": 0.0,
            "atk_speed_bonus_pct": 0,
            "spawns_adds": False,
            "fire_trails": False,
            "hp_pct": round(hp_pct * 100, 1)
        }
    elif hp_pct >= 0.30:
        return {
            "phase": 2,
            "name": "Фаза 2: Элементальный щит и призыв прислужников",
            "phase_mult": 1.25,
            "shield_pct": 0.25,
            "atk_speed_bonus_pct": 0,
            "spawns_adds": True,
            "fire_trails": False,
            "hp_pct": round(hp_pct * 100, 1)
        }
    else:
        return {
            "phase": 3,
            "name": "Фаза 3: Отчаянное Безумие (Desperation Mode)",
            "phase_mult": 1.55,
            "shield_pct": 0.0,
            "atk_speed_bonus_pct": 50,
            "spawns_adds": False,
            "fire_trails": True,
            "hp_pct": round(hp_pct * 100, 1)
        }


def calculate_boss_dynamic_damage(
    base_atk: int,
    difficulty: str = "normal",
    elapsed_seconds: float = 0.0,
    current_hp: int = 100,
    max_hp: int = 100,
    party_size: int = 1,
    target_defense: int = 0,
    pacifier_level: int = 0
) -> int:
    """
    Volume VII, 7.1: Master Damage Formula:
    Damage_boss = [BaseAtk * M_difficulty * M_enrage(t) * M_party * M_phase] - Defense_target
    """
    diff_key = difficulty.lower().strip()
    diff_cfg = BOSS_DIFFICULTIES.get(diff_key, BOSS_DIFFICULTIES["normal"])
    m_diff = float(diff_cfg["atk_mult"])

    m_enrage = calculate_enrage_multiplier(elapsed_seconds, pacifier_level=pacifier_level)
    m_party = 1.0 + max(0, party_size - 1) * 0.25

    phase_info = get_boss_phase_state(current_hp, max_hp)
    m_phase = float(phase_info["phase_mult"])

    gross_damage = base_atk * m_diff * m_enrage * m_party * m_phase
    net_damage = gross_damage - max(0, target_defense)

    return max(1, int(math.floor(net_damage)))
