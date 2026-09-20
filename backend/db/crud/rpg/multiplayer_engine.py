"""
natarGRP Multiplayer Engine — Threat & Aggro calculations, Party Synergies.
Conforms to Specification 3.0.0-ULTIMATE (Volume IX, 9.1 & 9.2).
"""
from typing import Dict, Any, List, Optional

# Маппинг героев к основным ролям и атрибутам для синергий группы
HERO_PRIMARY_ROLES: Dict[str, Dict[str, str]] = {
    "pudge": {"attribute": "strength", "role": "tank"},
    "wraith_king": {"attribute": "strength", "role": "tank"},
    "juggernaut": {"attribute": "agility", "role": "carry"},
    "phantom_assassin": {"attribute": "agility", "role": "carry"},
    "shadow_fiend": {"attribute": "agility", "role": "carry"},
    "anti_mage": {"attribute": "agility", "role": "carry"},
    "invoker": {"attribute": "intelligence", "role": "mage"},
    "leshrac": {"attribute": "intelligence", "role": "mage"},
}


def calculate_player_threat(
    damage_dealt: float = 0.0,
    taunt_mult: float = 1.0,
    distance: float = 200.0,
    heal_provided: float = 0.0
) -> float:
    """
    Volume IX, 9.1: Threat & Aggro Formula:
    Threat(P) = (DamageDealt * 1.0) + (TauntMultiplier * 4.0) + (1000 / max(1.0, Distance)) + (HealProvided * 0.6)
    """
    safe_dist = max(1.0, float(distance))
    threat = (
        (float(damage_dealt) * 1.0)
        + (float(taunt_mult) * 4.0)
        + (1000.0 / safe_dist)
        + (float(heal_provided) * 0.6)
    )
    return round(threat, 2)


def determine_boss_target(players_threat: Dict[str, float]) -> Optional[str]:
    """
    Volume IX, 9.1: Boss selects primary target with highest Threat value.
    Returns player_id or None if empty.
    """
    if not players_threat:
        return None
    return max(players_threat.keys(), key=lambda pid: players_threat[pid])


def calculate_party_synergies(hero_classes: List[str]) -> Dict[str, Any]:
    """
    Volume IX, 9.2: Party Synergies calculation based on hero classes in group:
    1. Holy Trinity (Танк + Керри + Маг): +35% party dmg, -20% boss incoming dmg.
    2. Dual Whirlwind (2+ Agility): +25% move speed, +15% dodge chance.
    3. Wall of Flesh (2+ Strength): Constant regen shield 15% of max HP.
    4. Arcane Rift (2+ Intelligence): +30% MP regen, -15% cooldown reduction.
    """
    if not hero_classes:
        return {
            "active_synergies": [],
            "party_damage_bonus_pct": 0.0,
            "incoming_damage_reduction_pct": 0.0,
            "move_speed_bonus_pct": 0.0,
            "dodge_bonus_pct": 0.0,
            "regen_shield_hp_pct": 0.0,
            "mp_regen_bonus_pct": 0.0,
            "cooldown_reduction_pct": 0.0,
            "counts": {"strength": 0, "agility": 0, "intelligence": 0, "tank": 0, "carry": 0, "mage": 0}
        }

    strength_count = 0
    agility_count = 0
    intel_count = 0
    tank_count = 0
    carry_count = 0
    mage_count = 0

    for h_class in hero_classes:
        key = str(h_class).lower().strip()
        info = HERO_PRIMARY_ROLES.get(key, {"attribute": "strength", "role": "tank"})
        attr = info["attribute"]
        role = info["role"]

        if attr == "strength":
            strength_count += 1
        elif attr == "agility":
            agility_count += 1
        elif attr == "intelligence":
            intel_count += 1

        if role == "tank":
            tank_count += 1
        elif role == "carry":
            carry_count += 1
        elif role == "mage":
            mage_count += 1

    active_synergies = []
    party_dmg = 0.0
    dmg_red = 0.0
    ms_bonus = 0.0
    dodge_bonus = 0.0
    shield_hp = 0.0
    mp_regen = 0.0
    cdr_bonus = 0.0

    # 1. Священная Троица (Holy Trinity)
    if tank_count >= 1 and carry_count >= 1 and mage_count >= 1:
        active_synergies.append({
            "id": "holy_trinity",
            "name": "Священная Троица (Танк + Керри + Маг)",
            "icon": "✨",
            "description": "+35% урона всей группе, -20% входящего урона от босса"
        })
        party_dmg += 35.0
        dmg_red += 20.0

    # 2. Двойной Вихрь (Dual Whirlwind)
    if agility_count >= 2:
        active_synergies.append({
            "id": "dual_whirlwind",
            "name": "Двойной Вихрь (2+ Ловкости)",
            "icon": "🌪️",
            "description": "+25% скорости бега, +15% уклонения от атак"
        })
        ms_bonus += 25.0
        dodge_bonus += 15.0

    # 3. Стена Плоти (Wall of Flesh)
    if strength_count >= 2:
        active_synergies.append({
            "id": "wall_of_flesh",
            "name": "Стена Плоти (2+ Силы)",
            "icon": "🛡️",
            "description": "Постоянный регенеративный щит на 15% от максимального HP"
        })
        shield_hp += 15.0

    # 4. Аркана Разлома (Arcane Rift)
    if intel_count >= 2:
        active_synergies.append({
            "id": "arcane_rift",
            "name": "Аркана Разлома (2+ Интеллекта)",
            "icon": "🔮",
            "description": "+30% регенерации маны, -15% ко всем кулдаунам"
        })
        mp_regen += 30.0
        cdr_bonus += 15.0

    return {
        "active_synergies": active_synergies,
        "party_damage_bonus_pct": party_dmg,
        "incoming_damage_reduction_pct": dmg_red,
        "move_speed_bonus_pct": ms_bonus,
        "dodge_bonus_pct": dodge_bonus,
        "regen_shield_hp_pct": shield_hp,
        "mp_regen_bonus_pct": mp_regen,
        "cooldown_reduction_pct": cdr_bonus,
        "counts": {
            "strength": strength_count,
            "agility": agility_count,
            "intelligence": intel_count,
            "tank": tank_count,
            "carry": carry_count,
            "mage": mage_count
        }
    }
