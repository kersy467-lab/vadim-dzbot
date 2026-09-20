import math
import random
from typing import Dict, Any, Tuple, Optional

# ==============================================================================
# 7 CANONICAL RARITY TIERS (Volume V of GDD)
# ==============================================================================

RARITY_TIERS: Dict[str, Dict[str, Any]] = {
    "common": {
        "id": "common",
        "name": "Обычный",
        "color": "#94a3b8",
        "multiplier": 1.00,
        "affixes_count": 0,
        "drop_weight": 50.0,
        "sell_base": 40,
    },
    "uncommon": {
        "id": "uncommon",
        "name": "Необычный",
        "color": "#22c55e",
        "multiplier": 1.30,
        "affixes_count": 1,
        "drop_weight": 28.0,
        "sell_base": 75,
    },
    "rare": {
        "id": "rare",
        "name": "Редкий",
        "color": "#3b82f6",
        "multiplier": 1.75,
        "affixes_count": 2,
        "drop_weight": 13.5,
        "sell_base": 140,
    },
    "epic": {
        "id": "epic",
        "name": "Эпический",
        "color": "#a855f7",
        "multiplier": 2.40,
        "affixes_count": 3,
        "drop_weight": 6.0,
        "sell_base": 350,
    },
    "legendary": {
        "id": "legendary",
        "name": "Легендарный",
        "color": "#f59e0b",
        "multiplier": 3.40,
        "affixes_count": 4,
        "drop_weight": 1.9,
        "sell_base": 900,
    },
    "mythic": {
        "id": "mythic",
        "name": "Мифический",
        "color": "#ef4444",
        "multiplier": 4.80,
        "affixes_count": 5,
        "drop_weight": 0.45,
        "sell_base": 2500,
    },
    "immortal": {
        "id": "immortal",
        "name": "Бессмертный",
        "color": "#ec4899",
        "multiplier": 6.80,
        "affixes_count": 6,
        "drop_weight": 0.15,
        "sell_base": 7500,
    },
}

FORGE_MAX_LEVEL = 100


def calculate_forge_multiplier(level: int) -> float:
    """
    Computes stat multiplier for forge level (+1..+100):
    - Level 0..15: +10% per level (1.0 -> 2.50x at +15)
    - Level 16..100: Compound +12.3% per level above 15, reaching ~48,000x at +100.
      Tuned specifically to balance working attack speed against original boss HP (1.2Q HP Enigma).
    """
    if level <= 0:
        return 1.0
    if level <= 15:
        return round(1.0 + (level * 0.10), 3)
    return round(2.50 * math.pow(1.123, level - 15), 2)


def get_forge_upgrade_requirements(current_level: int) -> Dict[str, Any]:
    """
    Returns success rate, gold and gem costs:
    - +1..+3: 100% success, (L+1) * 350 gold, 0 gems
    - +4..+6: 98% success, (L+1) * 800 gold, 2 gems
    - +7..+9: 90% success, (L+1) * 2000 gold, 6 gems
    - +10..+12: 75% success, (L+1) * 5500 gold, 15 gems
    - +13..+15: 60% success, (L+1) * 15000 gold, 45 gems
    - +16..+100: 50% success, (L+1) * 25000 gold, 45 + (L-15)*2 gems
    """
    cur_mult = calculate_forge_multiplier(current_level)
    if current_level >= FORGE_MAX_LEVEL:
        return {
            "current_level": current_level,
            "target_level": current_level,
            "is_max": True,
            "success_rate": 0.0,
            "success_pct": 0,
            "gold_cost": 0,
            "gems_cost": 0,
            "stat_multiplier": cur_mult,
            "current_multiplier": cur_mult,
        }

    target_level = current_level + 1
    if target_level <= 3:
        rate = 1.00
        gold = target_level * 350
        gems = 0
    elif target_level <= 6:
        rate = 0.98
        gold = target_level * 800
        gems = 2
    elif target_level <= 9:
        rate = 0.90
        gold = target_level * 2000
        gems = 6
    elif target_level <= 12:
        rate = 0.75
        gold = target_level * 5500
        gems = 15
    elif target_level <= 15:
        rate = 0.60
        gold = target_level * 15000
        gems = 45
    else:  # 16..100
        rate = 0.50
        gold = target_level * 25000
        gems = 45 + (target_level - 15) * 2

    return {
        "current_level": current_level,
        "target_level": target_level,
        "is_max": False,
        "success_rate": rate,
        "success_pct": int(rate * 100),
        "gold_cost": gold,
        "gems_cost": gems,
        "stat_multiplier": calculate_forge_multiplier(target_level),
        "current_multiplier": cur_mult,
    }


def apply_forge_upgrade_to_item(item: Dict[str, Any], target_level: int) -> Dict[str, Any]:
    """
    Recalculates item stats for target_level (+1..+100):
    Stat_final = Stat_base * calculate_forge_multiplier(Level) * M_rarity
    """
    from backend.db.crud.rpg.loot import rebuild_item_description

    cur_lvl = item.get("upgrade", 0)
    cur_mult = max(1.0, calculate_forge_multiplier(cur_lvl))

    item["upgrade"] = target_level
    item["forge_level"] = target_level
    growth_mult = calculate_forge_multiplier(target_level)

    # 1. Base Weapon Attack
    if "base_min" not in item and "min_atk" in item:
        item["base_min"] = max(6, int(round(item["min_atk"] / cur_mult)))
    if "base_max" not in item and "max_atk" in item:
        item["base_max"] = max(10, int(round(item["max_atk"] / cur_mult)))

    if "base_min" in item:
        item["min_atk"] = int(round(item["base_min"] * growth_mult))
    if "base_max" in item:
        item["max_atk"] = max(item.get("min_atk", 8) + 4, int(round(item["base_max"] * growth_mult)))

    # 2. Base Armor Defense & HP
    if "base_def" not in item and ("defense" in item or "def" in item):
        cur_d = item.get("defense", item.get("def", 4))
        item["base_def"] = max(2, int(round(cur_d / cur_mult)))
    if "base_hp" not in item and "hp_bonus" in item:
        item["base_hp"] = max(15, int(round(item["hp_bonus"] / cur_mult)))

    if "base_def" in item:
        new_def = int(round(item["base_def"] * growth_mult))
        item["defense"] = new_def
        if "def" in item:
            item["def"] = new_def
    if "base_hp" in item:
        item["hp_bonus"] = int(round(item["base_hp"] * growth_mult))

    # 3. Bonus Attributes & Special Affixes Preservation
    bonus = dict(item.get("bonus", {}))
    if "base_bonus" not in item:
        item["base_bonus"] = dict(bonus)

    base_b = item["base_bonus"]
    for k, v in base_b.items():
        if isinstance(v, (int, float)) and v > 0:
            if k in ["str", "agi", "int", "atk", "all_stats"]:
                bonus[k] = int(round(v * growth_mult))
            elif k in ["hp", "mp"]:
                bonus[k] = int(round(v * growth_mult))
            elif k in ["crit", "dodge", "lifesteal", "atk_speed"]:
                bonus[k] = min(45, int(round(v * (1.0 + target_level * 0.04))))
            elif k in ["ult_boost"]:
                bonus[k] = min(120, int(round(v * (1.0 + target_level * 0.04))))
            elif k in ["ult_cd", "cooldown_reduct"]:
                bonus[k] = min(50, int(round(v * (1.0 + target_level * 0.03))))
            elif k in ["spell_amp"]:
                bonus[k] = min(50, int(round(v * (1.0 + target_level * 0.04))))
            elif k in ["freeze_chance", "slow_enemy", "silence_enemy", "stun_chance", "illusion_evade", "ethereal_evade"]:
                bonus[k] = min(60, int(round(v * (1.0 + target_level * 0.06))))
            elif k in ["magic_resist"]:
                bonus[k] = min(75, int(round(v * (1.0 + target_level * 0.08))))
            elif k in [
                "lightning", "chain_lightning", "burst_magic", "cleave", "reflect", "damage_block", "block",
                "pure_dmg", "meteor", "rot_aura", "water_surge", "chaos_burst", "ghost_strike", "black_hole",
                "fire_aura", "burn", "frost_armor", "regen", "hp_regen", "mp_regen", "armor_reduction",
                "weaken", "soul_steal", "execute_low_hp", "spell_lifesteal", "crit_multiplier", "magic_dmg",
                "armor_pierce", "creep_dmg", "giant_stomp", "double_strike", "gold_boost"
            ]:
                bonus[k] = int(round(v * growth_mult))
            else:
                bonus[k] = int(round(v * growth_mult))
        else:
            bonus[k] = v

    item["bonus"] = bonus
    item["bonus_desc"] = rebuild_item_description(item)
    return item
