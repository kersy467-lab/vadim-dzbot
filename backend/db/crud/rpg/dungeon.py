"""
natarGRP Dungeon — main wave runner.
Exposes run_dungeon_wave() which the API router calls.
"""
import random
import uuid
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.db.models import RPGCharacter
from backend.db.crud.rpg.character import (
    calculate_character_effective_stats,
    serialize_character_profile,
    get_or_create_rpg_character,
)
from backend.db.crud.rpg.creeps import NATAR_CREEPS_POOL, NATAR_FLOOR_BOSSES
from backend.db.crud.rpg.loot import generate_random_natar_item, pick_smart_loot_item
from backend.db.crud.rpg.items_catalog import RARITY_MULTIPLIERS
from backend.db.crud.rpg.chests import open_wave_chest, open_boss_raid_chest
from backend.db.crud.rpg.shop import add_xp_and_gold_to_character
from backend.db.crud.rpg.dungeon_core import build_enemy, simulate_combat

KILL_STREAK_TITLES = [
    "KILLING SPREE! ⚡",
    "DOMINATING! 🔥",
    "MEGA KILL! 💥",
    "UNSTOPPABLE! ⚔️",
    "WICKED SICK! ☠️",
    "MONSTER KILL! 👹",
    "GODLIKE! 👑",
    "HOLY SHIT! 🌟",
    "RAMPAGE! 🏆"
]

FLOOR_BOSS_ORDER = [
    "golem", "lich", "tormentor", "dragon", "roshan", "tidehunter",
    "sf_boss", "necrophos", "invoker_boss", "chaos_knight",
    "dark_tormentor", "doom", "primal_beast", "phantom_roshan", "enigma"
]


async def run_dungeon_wave(
    session: AsyncSession,
    char: RPGCharacter,
    user_name: str = "Герой"
) -> Dict[str, Any]:
    """
    Runs one wave of the endless dungeon.
    Returns a result dict with combat details, rewards, and updated character profile.
    """
    stats = calculate_character_effective_stats(char)
    floor = char.dungeon_floor
    wave_num = (char.dungeon_cleared % 20) + 1
    is_boss_wave = (wave_num == 20)

    # Build enemy with exponential floor scaling
    floor_scale = (1.18 ** max(0, floor - 1))
    creep_scale = (1.18 ** max(0, floor - 1))
    creep_atk_scale = (1.15 ** max(0, floor - 1))
    boss_atk_scale = (1.18 ** max(0, floor - 1))

    gold_scale = 1.0 + (floor - 1) * 0.08
    if is_boss_wave:
        available_creeps = [c for c in NATAR_CREEPS_POOL if c.get("floor_min", 1) <= floor]
        if not available_creeps:
            available_creeps = NATAR_CREEPS_POOL
        target_template = random.choice(available_creeps)
        enemy_name = f"БОСС ВОЛНЫ: {target_template['name']}"
        enemy_icon = "👑"
        enemy_hp = int(target_template["base_hp"] * 15 * creep_scale)
        enemy_atk = int(target_template["base_atk"] * 10 * creep_atk_scale)
        enemy_def = int(target_template["base_def"] + (floor - 1) * 3)
        base_gold = int(target_template["gold"] * 5 * gold_scale)
        base_xp = int(target_template["xp"] * 4 * gold_scale)
    else:
        available_creeps = [c for c in NATAR_CREEPS_POOL if c.get("floor_min", 1) <= floor]
        if not available_creeps:
            available_creeps = NATAR_CREEPS_POOL
        target_template = random.choice(available_creeps)
        creep_count = random.randint(2, 4)
        enemy_name = f"Пачка: {creep_count}x {target_template['name']}"
        enemy_icon = target_template["icon"]
        enemy_hp = int((target_template["base_hp"] * creep_count) * creep_scale)
        enemy_atk = int((target_template["base_atk"] + creep_count * 2) * creep_atk_scale)
        enemy_def = int(target_template["base_def"] + (floor - 1) * 2)
        base_gold = int((target_template["gold"] * creep_count) * gold_scale)
        base_xp = int((target_template["xp"] * creep_count) * gold_scale)

    # Simulate combat
    hero_hp = stats["hp_max"]
    e_hp = enemy_hp
    combat_log = []
    total_dmg_dealt = 0
    hero_crits = 0

    spell_amp = (stats.get("mp_max", 100) * 0.002) + (stats.get("spell_amp", 0) / 100.0)
    lifesteal_pct = stats.get("lifesteal", 0)
    crit_chance = stats.get("crit_chance", 15)
    dodge_chance = stats.get("dodge_chance", 5)
    h_def = max(0, stats.get("defense", 5))
    h_dr = min(0.82, (h_def * 0.05) / (1.0 + h_def * 0.05 + floor * 0.4))
    e_dr = min(0.85, (max(0, enemy_def) * 0.05) / (1.0 + max(0, enemy_def) * 0.05))
    reflect_pct = stats.get("reflect", 0)
    bonus_flat_magic = stats.get("burst_magic", 0) + stats.get("lightning", 0)

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
            base_h = int(base_h * 2.2)

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
                combat_log.append(f"💥 {enemy_name} нанес {in_dmg} урона. Отражено {ref_dmg} урона!")
            else:
                combat_log.append(f"💥 {enemy_name} нанес вам {in_dmg} урона.")

    victory = (e_hp <= 0)
    hero_dead = (hero_hp <= 0)
    is_timeout = (not victory and not hero_dead)

    if victory:
        char.dungeon_cleared += 1
        gold_earned = base_gold + random.randint(15, 35)
        xp_earned = base_xp + random.randint(15, 35)
        streak_title = random.choice(KILL_STREAK_TITLES)

        chest_reward = None
        item_dropped = None

        if is_boss_wave:
            cur_boss_id = FLOOR_BOSS_ORDER[min(len(FLOOR_BOSS_ORDER) - 1, max(0, floor - 1))]
            chest_reward = await open_boss_raid_chest(session, char, boss_id=cur_boss_id)
            item_dropped = chest_reward.get("item")
        elif char.dungeon_cleared % 10 == 0:
            if char.dungeon_cleared % 20 == 0:
                f_idx = (char.dungeon_cleared // 20) - 1
                cur_boss_id = FLOOR_BOSS_ORDER[min(len(FLOOR_BOSS_ORDER) - 1, max(0, f_idx))]
                chest_reward = await open_boss_raid_chest(session, char, boss_id=cur_boss_id)
            else:
                chest_reward = await open_wave_chest(session, char, char.dungeon_cleared)
            item_dropped = chest_reward.get("item") if chest_reward else None

        if is_boss_wave:
            char.dungeon_floor += 1
            char.boss_kills = getattr(char, "boss_kills", 0) + 1

        leveled_up, new_lvl = await add_xp_and_gold_to_character(session, char, xp_earned, gold_earned)

        return {
            "victory": True,
            "is_boss": is_boss_wave,
            "is_draw": False,
            "enemy_name": enemy_name,
            "enemy_icon": enemy_icon,
            "streak_title": streak_title,
            "floor": char.dungeon_floor,
            "wave": wave_num,
            "total_damage": total_dmg_dealt,
            "crits_count": hero_crits,
            "gold_earned": gold_earned,
            "xp_earned": xp_earned,
            "chest_reward": chest_reward,
            "item_dropped": item_dropped,
            "leveled_up": leveled_up,
            "hero_hp_left": max(1, hero_hp),
            "hero_hp_max": stats["hp_max"],
            "enemy_hp_left": 0,
            "enemy_hp_max": enemy_hp,
            "rounds_fought": rounds,
            "combat_log": combat_log[-6:],
            "profile": serialize_character_profile(char, user_name=user_name)
        }
    elif is_timeout:
        return {
            "victory": False,
            "is_boss": is_boss_wave,
            "is_draw": True,
            "enemy_name": enemy_name,
            "enemy_icon": enemy_icon,
            "description": f"⏳ Бой затянулся ({rounds} раундов)! Босс выстоял с {max(0, e_hp):,} HP. У вас осталось {max(0, hero_hp):,} HP. Улучшите атаку в Кузнице!",
            "hero_hp_left": max(0, hero_hp),
            "hero_hp_max": stats["hp_max"],
            "enemy_hp_left": max(0, e_hp),
            "enemy_hp_max": enemy_hp,
            "rounds_fought": rounds,
            "combat_log": combat_log[-6:],
            "profile": serialize_character_profile(char, user_name=user_name)
        }
    else:
        return {
            "victory": False,
            "is_boss": is_boss_wave,
            "is_draw": False,
            "enemy_name": enemy_name,
            "enemy_icon": enemy_icon,
            "description": f"💀 Герой пал на {rounds} раунде боя! (Нанесено {total_dmg_dealt:,} урона боссу). Повысьте броню и здоровье!",
            "hero_hp_left": 0,
            "hero_hp_max": stats["hp_max"],
            "enemy_hp_left": max(0, e_hp),
            "enemy_hp_max": enemy_hp,
            "rounds_fought": rounds,
            "combat_log": combat_log[-6:],
            "profile": serialize_character_profile(char, user_name=user_name)
        }
