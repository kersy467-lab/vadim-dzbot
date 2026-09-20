import math
import random
from typing import Dict, Any, List
from backend.db.models import RPGCharacter
from backend.db.crud.rpg.heroes import NATAR_HEROES
from backend.db.crud.rpg.pets_config import PETS_CATALOG
from backend.db.crud.rpg.rebirth import calculate_rebirth_multiplier
from backend.db.crud.rpg.talent_tree import get_hero_tree


def calculate_character_effective_stats(char: RPGCharacter) -> Dict[str, Any]:
    """
    Calculates final attributes, ATK, DEF, HP, MP using the 3-attribute system:
      - Сила (Strength): +22 HP за очко, +0.35 HP/сек регенерация
      - Ловкость (Agility): +0.025 скорости атаки, +0.4 брони, криты, уклонение
      - Интеллект (Intelligence): +14 маны за очко, +0.25 MP/сек регенерация, +0.4% сопр. магии
      - Основной атрибут героя (Primary Attr): +1 к базовому урону атаки за каждое очко!
    """
    h_class = str(getattr(char, "hero_class", "pudge") or "pudge").strip().lower()
    legacy_map = {
        "warrior": "juggernaut",
        "knight": "pudge",
        "paladin": "wraith_king",
        "archer": "phantom_assassin",
        "rogue": "phantom_assassin",
        "assassin": "phantom_assassin",
        "mage": "invoker",
        "wizard": "invoker"
    }
    canonical_class = legacy_map.get(h_class, h_class)
    hero_cfg = NATAR_HEROES.get(canonical_class, NATAR_HEROES["pudge"])

    # Base attributes from character allocation
    str_val = int(char.strength)
    agi_val = int(char.agility)
    int_val = int(char.intelligence)

    # Equipment slots (supports both legacy weapon/armor/relic and generic slot_1..slot_6)
    eq = char.equipment or {}
    equipped_items = [it for it in eq.values() if it and isinstance(it, dict)]

    # Accumulate all equipment bonuses
    gear_str = 0
    gear_agi = 0
    gear_int = 0
    ult_boost = 0
    ult_cd_reduct = 0
    flat_spell_amp = 0
    flat_hp = 0
    flat_mp = 0
    flat_atk = 0
    flat_def = 0
    flat_atk_speed = 0.0
    crit_chance = 0
    dodge_chance = 0
    lifesteal = 0
    magic_res = 0
    damage_block = 0
    reflect = 0
    flat_hp_regen = 0.0
    flat_mp_regen = 0.0
    w_min = 8
    w_max = 14
    has_custom_weapon = False

    for slot_item in equipped_items:
        sb = slot_item.get("bonus", {})
        all_s = sb.get("all_stats", 0)
        gear_str += sb.get("str", 0) + all_s
        gear_agi += sb.get("agi", 0) + all_s
        gear_int += sb.get("int", 0) + all_s

        ult_boost += sb.get("ult_boost", 0)
        ult_cd_reduct += sb.get("ult_cd", 0) + sb.get("cooldown_reduct", 0)
        flat_spell_amp += sb.get("spell_amp", 0)
        flat_hp += sb.get("hp", 0)
        flat_mp += sb.get("mp", 0)
        flat_atk += sb.get("atk", 0)
        flat_def += sb.get("defense", 0) + sb.get("def", 0) + sb.get("aura_armor", 0) + sb.get("armor_aura", 0)
        flat_atk_speed += (sb.get("atk_speed", 0) * 0.01) + (sb.get("speed", 0) * 0.01)
        crit_chance += sb.get("crit", 0) + sb.get("crit_chance", 0)
        dodge_chance += sb.get("dodge", 0)
        lifesteal += sb.get("lifesteal", 0)
        magic_res += sb.get("magic_resist", 0)
        damage_block += sb.get("damage_block", 0) + sb.get("block", 0)
        reflect += sb.get("reflect", 0)
        flat_hp_regen += sb.get("hp_regen", 0)
        flat_mp_regen += sb.get("mp_regen", 0)

        # Inherent item defense / hp / attack stats
        item_type = slot_item.get("type") or slot_item.get("slot")
        if item_type == "weapon" or "min_atk" in slot_item:
            if not has_custom_weapon:
                w_min = slot_item.get("min_atk") or slot_item.get("base_min") or 8
                w_max = slot_item.get("max_atk") or slot_item.get("base_max") or 14
                has_custom_weapon = True
            else:
                w_min += slot_item.get("min_atk") or slot_item.get("base_min") or 0
                w_max += slot_item.get("max_atk") or slot_item.get("base_max") or 0

        if item_type == "armor" or "defense" in slot_item:
            flat_def += slot_item.get("defense") or slot_item.get("base_def") or slot_item.get("def") or 0
            flat_hp += slot_item.get("hp_bonus") or slot_item.get("base_hp") or 0

    if canonical_class == "wraith_king":
        lifesteal += 15
    if canonical_class == "pudge":
        flat_hp_regen += 2.5

    talents = getattr(char, "talents", {}) or {}
    constellations = talents.get("constellations", {}) or {}
    vit_level = constellations.get("constellation_vitality", 0)
    flat_hp += vit_level * 150
    flat_def += vit_level * 5

    # New hero-specific talent tree bonuses (applied BEFORE stat formulas)
    _tree_talents = (talents.get("tree") or {}).get(canonical_class, {})
    _flat_mp_regen_from_tree = 0.0
    _flat_atk_pct_str = 0.0
    _hp_to_crit = 0.0
    _unlocked_perks = []
    _hero_tree = {}
    _flask_heal_flat = 0
    _flask_heal_pct = 0.0
    _flask_mana = 0
    _flask_cd_reduct = 0
    if _tree_talents:
        _hero_tree = get_hero_tree(canonical_class)
        for _nid, _nlvl in _tree_talents.items():
            if not _nlvl:
                continue
            _ncfg = _hero_tree.get(_nid)
            if not _ncfg:
                continue
            _eff = _ncfg.get("effect", {})
            if "perk" in _eff and _eff["perk"]:
                _unlocked_perks.append(_eff["perk"])
            flat_hp += _eff.get("flat_hp", 0)
            flat_mp += _eff.get("flat_mp", 0)
            flat_atk += _eff.get("flat_atk", 0)
            flat_def += _eff.get("flat_def", 0)
            flat_hp_regen += _eff.get("flat_hp_regen", 0.0)
            _flat_mp_regen_from_tree += _eff.get("flat_mp_regen", 0.0)
            _flat_atk_pct_str += _eff.get("flat_atk_pct_str", 0.0)
            _hp_to_crit += _eff.get("hp_to_crit", 0.0)
            flat_atk_speed += _eff.get("flat_atk_speed", 0.0)
            crit_chance += _eff.get("crit_chance", 0)
            dodge_chance += _eff.get("dodge_chance", 0)
            lifesteal += _eff.get("lifesteal", 0)
            magic_res += _eff.get("magic_res", 0)
            damage_block += _eff.get("damage_block", 0)
            flat_spell_amp += _eff.get("spell_amp", 0)
            ult_cd_reduct += _eff.get("ult_cd_reduct", 0)
            _flask_heal_flat += _eff.get("flask_heal_flat", 0)
            _flask_heal_pct += _eff.get("flask_heal_pct", 0.0)
            _flask_mana += _eff.get("flask_mana", 0)
            _flask_cd_reduct += _eff.get("flask_cd_reduct", 0)

    total_str = str_val + gear_str
    total_agi = agi_val + gear_agi
    total_int = int_val + gear_int

    # Attributes scaling (Volume III GDD formulas)
    stat_hp = hero_cfg.get("base_hp", 150) + int(total_str * 24) + flat_hp
    stat_hp_regen = round(0.5 + min(800.0, total_str * 0.06) + flat_hp_regen, 1)

    stat_atk_speed = min(4.0, round(1.0 + (total_agi * 0.012) + flat_atk_speed, 2))
    stat_def = int(math.floor(total_agi * 0.18)) + flat_def
    crit_chance = min(85, round(5.0 + (total_agi * 0.10) + crit_chance + (stat_hp * _hp_to_crit), 1))
    dodge_chance = min(60, int(total_agi * 0.25) + dodge_chance)

    stat_mp = hero_cfg.get("base_mp", 100) + int(total_int * 16) + flat_mp
    stat_mp_regen = round(1.0 + (total_int * 0.10) + flat_mp_regen + _flat_mp_regen_from_tree, 1)
    magic_res = min(80, int(total_int * 0.35) + magic_res)

    # Primary attribute attack bonus (1.5x tuned with working attack speed)
    if hero_cfg["attr"] == "Сила":
        primary_bonus = total_str * 1.5
    elif hero_cfg["attr"] == "Ловкость":
        primary_bonus = total_agi * 1.5
    else:  # Интеллект
        primary_bonus = total_int * 1.5

    stat_atk = int(primary_bonus + (total_str * _flat_atk_pct_str)) + flat_atk
    total_min_atk = stat_atk + w_min
    total_max_atk = stat_atk + w_max

    # Spell Amplification: 1.5% per intelligence point + flat gear spell amp
    spell_amp = round(total_int * 1.5 + flat_spell_amp, 1)

    gear_score = int(
        (total_min_atk + total_max_atk) * 1.5
        + stat_def * 3.0
        + stat_hp * 0.35
        + stat_mp * 0.3
        + crit_chance * 3.0
        + int(stat_atk_speed * 40)
    )

    is_mage = canonical_class in ("invoker", "mage", "wizard")
    damage_type = "magical" if is_mage else "physical"

    # Endgame RPG multipliers
    rebirths = getattr(char, "rebirths", 0)
    rebirth_mult = calculate_rebirth_multiplier(rebirths)

    talent_lifesteal = talents.get("lifesteal", 0) * 2
    talent_dodge = talents.get("dodge", 0) * 4
    talent_crit_mult = talents.get("crit_mult", 0) * 25   # +25% crit multiplier per level
    talent_cooldown = talents.get("cooldown", 0) * 6       # -6% cooldown reduction per level
    # Accumulate crit_mult bonus from tree nodes (use already-built _hero_tree)
    _tree_crit_mult_bonus = 0
    if _tree_talents:
        for _nid2, _nlvl2 in _tree_talents.items():
            if _nlvl2:
                _nc2 = _hero_tree.get(_nid2)  # _hero_tree always set when _tree_talents truthy
                if _nc2:
                    _tree_crit_mult_bonus += _nc2.get("effect", {}).get("crit_mult_bonus", 0)
    talent_crit_mult += _tree_crit_mult_bonus

    # Pet Multipliers (boosted by Constellation Pet)
    pet_constellation_boost = 1.0 + (constellations.get("constellation_pet", 0) * 0.20)
    pet_hp_mult = 1.0 * pet_constellation_boost
    pet_dmg_mult = 1.0 * pet_constellation_boost
    pet_gold_mult = 1.0
    pet_xp_mult = 1.0

    try:
        pets = getattr(char, "pets", []) or []
        for p in pets:
            if p.get("is_equipped"):
                pet_cfg = PETS_CATALOG.get(p.get("type"))
                if pet_cfg:
                    stars = p.get("stars", 1)
                    s_mult = 1.0 + (stars - 1) * pet_cfg.get("stars_scaling", 0.08)
                    pet_hp_mult *= (pet_cfg.get("base_hp_mult", 1.0) * s_mult)
                    pet_dmg_mult *= (pet_cfg.get("base_dmg_mult", 1.0) * s_mult)
                    pet_gold_mult *= (pet_cfg.get("base_gold_mult", 1.0) * s_mult)
                    pet_xp_mult *= (pet_cfg.get("base_xp_mult", 1.0) * s_mult)
    except Exception:
        pass

    # Apply rebirth and pet multipliers to core stats
    stat_hp = int(stat_hp * rebirth_mult * pet_hp_mult)
    total_min_atk = int(total_min_atk * rebirth_mult * pet_dmg_mult)
    total_max_atk = int(total_max_atk * rebirth_mult * pet_dmg_mult)

    return {
        "hp_max": stat_hp,
        "mp_max": stat_mp,
        "hp_regen": stat_hp_regen,
        "mp_regen": stat_mp_regen,
        "min_atk": total_min_atk,
        "max_atk": total_max_atk,
        "defense": stat_def,
        "attack_speed": stat_atk_speed,
        "magic_resist": magic_res,
        "crit_chance": crit_chance,
        "dodge_chance": dodge_chance + talent_dodge,
        "lifesteal": min(60, lifesteal + talent_lifesteal),
        "damage_block": damage_block,
        "reflect": min(100, reflect),
        "gear_score": gear_score,
        "primary_attr": hero_cfg.get("attr", "Сила"),
        "primary_damage_bonus": int(primary_bonus),
        "spell_amp": spell_amp,
        "ult_boost": ult_boost,
        "ult_cd_reduct": min(60, ult_cd_reduct + talent_cooldown),
        "crit_mult_bonus": talent_crit_mult,
        "damage_type": damage_type,
        "pet_gold_mult": pet_gold_mult,
        "pet_xp_mult": pet_xp_mult,
        "skill": hero_cfg.get("skill", {"name": "Навык", "icon": "⚡", "mp_cost": 20, "desc": "Навык героя"}),
        "rebirth_multiplier": rebirth_mult,
        "perks": _unlocked_perks,
        "flask_heal_flat": _flask_heal_flat,
        "flask_heal_pct": round(_flask_heal_pct, 2),
        "flask_mana": _flask_mana,
        "flask_cd_reduct": _flask_cd_reduct,
        "constellations_bonuses": {
            "vitality_hp": vit_level * 150,
            "vitality_armor": vit_level * 5,
            "pet_power_pct": constellations.get("constellation_pet", 0) * 20,
            "drop_fortune_pct": constellations.get("constellation_fortune", 0) * 18,
            "enrage_slow_pct": constellations.get("constellation_boss_pacifier", 0) * 14,
            "coop_damage_pct": constellations.get("constellation_brotherhood", 0) * 20,
            "colossus_damage_pct": constellations.get("constellation_colossus_slayer", 0) * 30,
        },
        "base_strength": str_val,
        "base_agility": agi_val,
        "base_intelligence": int_val,
        "gear_strength": gear_str,
        "gear_agility": gear_agi,
        "gear_intelligence": gear_int,
        "total_strength": total_str,
        "total_agility": total_agi,
        "total_intelligence": total_int
    }
