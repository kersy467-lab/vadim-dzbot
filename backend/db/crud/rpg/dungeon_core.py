"""
natarGRP Dungeon Core — wave simulation helper functions.
These are shared utilities used by dungeon.py (the main wave runner).
"""
import random
import uuid
from typing import Optional, Dict, Any, List, Tuple

from backend.db.models import RPGCharacter
from backend.db.crud.rpg.character import calculate_character_effective_stats
from backend.db.crud.rpg.creeps import NATAR_CREEPS_POOL, NATAR_FLOOR_BOSSES


def pick_floor_boss(floor: int) -> Dict[str, Any]:
    """Returns a floor boss template for the given dungeon floor."""
    idx = max(0, min(len(NATAR_FLOOR_BOSSES) - 1, floor - 1))
    return NATAR_FLOOR_BOSSES[idx]


def pick_floor_creep(floor: int) -> Dict[str, Any]:
    """Picks a random creep appropriate for the given floor."""
    available = [c for c in NATAR_CREEPS_POOL if c.get("floor_min", 1) <= floor]
    if not available:
        available = NATAR_CREEPS_POOL
    return random.choice(available)


def compute_combat_scales(floor: int) -> Tuple[float, float, float, float]:
    """
    Returns (floor_scale, creep_scale, creep_atk_scale, boss_atk_scale)
    used for exponential scaling of enemy stats.
    """
    floor_scale = 1.18 ** max(0, floor - 1)
    creep_scale = 1.18 ** max(0, floor - 1)
    creep_atk_scale = 1.15 ** max(0, floor - 1)
    boss_atk_scale = 1.18 ** max(0, floor - 1)
    return floor_scale, creep_scale, creep_atk_scale, boss_atk_scale


def build_enemy(floor: int, wave_num: int) -> Dict[str, Any]:
    """
    Constructs enemy stats dict for the given floor and wave number.
    Wave 20 (is_boss_wave) spawns a floor boss; otherwise spawns a creep pack.

    Returns: dict with keys: name, icon, hp, atk, def_, gold, xp, is_boss
    """
    is_boss_wave = (wave_num == 20)
    floor_scale, creep_scale, creep_atk_scale, boss_atk_scale = compute_combat_scales(floor)

    if is_boss_wave:
        tmpl = pick_floor_boss(floor)
        enemy_name = f"{tmpl['name']} [Этаж {floor}]"
        enemy_icon = tmpl["icon"]
        enemy_hp = int(tmpl["base_hp"] * floor_scale)
        enemy_atk = int(tmpl["base_atk"] * boss_atk_scale)
        enemy_def = int(tmpl["base_def"] + (floor - 1) * 3)
        base_gold = int(tmpl["gold"] * (1.0 + (floor - 1) * 0.15))
        base_xp = int(tmpl["xp"] * (1.0 + (floor - 1) * 0.15))
    else:
        tmpl = pick_floor_creep(floor)
        creep_count = random.randint(2, 4)
        enemy_name = f"Пачка: {creep_count}x {tmpl['name']}"
        enemy_icon = tmpl["icon"]
        enemy_hp = int((tmpl["base_hp"] * creep_count) * creep_scale)
        enemy_atk = int((tmpl["base_atk"] + creep_count * 2) * creep_atk_scale)
        enemy_def = int(tmpl["base_def"] + (floor - 1) * 2)
        base_gold = int((tmpl["gold"] * creep_count) * (1.0 + (floor - 1) * 0.12))
        base_xp = int((tmpl["xp"] * creep_count) * (1.0 + (floor - 1) * 0.12))

    return {
        "name": enemy_name,
        "icon": enemy_icon,
        "hp": enemy_hp,
        "atk": enemy_atk,
        "def_": enemy_def,
        "gold": base_gold,
        "xp": base_xp,
        "is_boss": is_boss_wave
    }


def simulate_combat(
    stats: Dict[str, Any],
    enemy: Dict[str, Any],
    user_name: str = "Герой"
) -> Tuple[bool, bool, int, int, int, List[str]]:
    """
    Simulates fast tactical combat between hero and enemy.
    Returns: (victory, is_timeout, total_dmg_dealt, hero_crits, rounds, combat_log)
    """
    floor = 1  # used for diminishing returns inside enemy def
    hero_hp = stats["hp_max"]
    e_hp = enemy["hp"]
    enemy_atk = enemy["atk"]
    enemy_def = enemy["def_"]

    spell_amp = (stats.get("mp_max", 100) * 0.002) + (stats.get("spell_amp", 0) / 100.0)
    lifesteal_pct = stats.get("lifesteal", 0)
    crit_chance = stats.get("crit_chance", 15)
    dodge_chance = stats.get("dodge_chance", 5)
    h_def = max(0, stats.get("defense", 5))

    h_dr = min(0.82, (h_def * 0.05) / (1.0 + h_def * 0.05))
    e_dr = min(0.85, (max(0, enemy_def) * 0.05) / (1.0 + max(0, enemy_def) * 0.05))
    reflect_pct = stats.get("reflect", 0)
    bonus_flat_magic = stats.get("burst_magic", 0) + stats.get("lightning", 0)

    combat_log: List[str] = []
    total_dmg_dealt = 0
    hero_crits = 0
    rounds = 0
    max_rounds = 400

    while hero_hp > 0 and e_hp > 0 and rounds < max_rounds:
        rounds += 1
        base_h = random.randint(stats["min_atk"], stats["max_atk"])
        skill_name = "Базовый удар"

        if rounds % 6 == 0:
            skill_name = "Ультимейт (Колоссальный урон)"
            ult_amp = 1.0 + (stats.get("ult_boost", 0) / 100.0)
            base_h = int(base_h * 5.5 * (1.0 + spell_amp) * ult_amp)
        elif rounds % 3 == 0:
            skill_name = "Боевой навык (Скилл 1)"
            base_h = int(base_h * 3.5 * (1.0 + spell_amp))

        is_crit = (random.randint(1, 100) <= crit_chance)
        if is_crit:
            hero_crits += 1
            crit_mult = 2.2 + (stats.get("crit_mult_bonus", 0) / 100.0)
            base_h = int(base_h * crit_mult)

        base_h += bonus_flat_magic
        dmg_out = max(10, int(base_h * (1.0 - e_dr)))
        e_hp -= dmg_out
        total_dmg_dealt += dmg_out

        if lifesteal_pct > 0:
            ls_heal = int(dmg_out * (lifesteal_pct / 100.0))
            hero_hp = min(stats["hp_max"], hero_hp + ls_heal)

        if e_hp <= 0:
            combat_log.append(f"⚔️ {skill_name}: {dmg_out} урона. Враг повержен!")
            break

        is_dodge = (random.randint(1, 100) <= dodge_chance)
        if is_dodge:
            combat_log.append(f"💨 {user_name} ловко увернулся от удара!")
        else:
            in_dmg = max(5, int(enemy_atk * (1.0 - h_dr)))
            hero_hp -= in_dmg
            if reflect_pct > 0:
                ref_dmg = int(in_dmg * (reflect_pct / 100.0))
                e_hp -= ref_dmg
                combat_log.append(f"💥 {enemy['name']} нанес {in_dmg} урона. Отражено {ref_dmg} урона!")
            else:
                combat_log.append(f"💥 {enemy['name']} нанес вам {in_dmg} урона.")

    victory = (e_hp <= 0)
    hero_dead = (hero_hp <= 0)
    is_timeout = (not victory and not hero_dead)
    return victory, is_timeout, total_dmg_dealt, hero_crits, rounds, combat_log[-6:], hero_hp, e_hp
