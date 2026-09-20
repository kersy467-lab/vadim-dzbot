"""
natarGRP Creeps 2D State Machine AI & Auras Engine.
Conforms to Specification 3.0.0-ULTIMATE (Volume VI, 6.1 & 6.2).
"""
import math
import uuid
from typing import Dict, Any, List, Optional
from backend.db.crud.rpg.creeps import DOTA_BESTIARY_CATALOG

AGGRO_RADIUS = 450.0  # Радиус обнаружения игрока (Volume VI, 6.1)
LEASH_RADIUS = 650.0  # Радиус потери цели


def create_creep_instance(creep_id: str, x: float = 0.0, y: float = 0.0) -> Dict[str, Any]:
    """Instantiates a creep with initial State Machine AI parameters."""
    tmpl = DOTA_BESTIARY_CATALOG.get(creep_id, DOTA_BESTIARY_CATALOG["melee_creep"])
    return {
        "instance_id": f"{creep_id}_{uuid.uuid4().hex[:6]}",
        "type_id": tmpl["id"],
        "name": tmpl["name"],
        "role": tmpl["role"],
        "icon": tmpl["icon"],
        "hp": tmpl["hp"],
        "max_hp": tmpl["hp"],
        "base_attack": tmpl["attack"],
        "effective_attack": tmpl["attack"],
        "armor": tmpl["armor"],
        "speed": tmpl["speed"],
        "attack_range": tmpl["attack_range"],
        "attack_cooldown": tmpl["attack_cooldown"],
        "current_cooldown": 0.0,
        "ability_cooldown": 0.0,
        "ai_state": "SPAWN",  # SPAWN -> IDLE -> CHASE -> ATTACK -> COOLDOWN
        "spawn_timer": 0.5,
        "x": float(x),
        "y": float(y),
        "target_x": float(x),
        "target_y": float(y),
        "is_alive": True,
        "active_auras": [],
        "ability": tmpl.get("ability"),
        "aura": tmpl.get("aura"),
        "on_death": tmpl.get("on_death"),
        "micro_stun_immune": tmpl.get("micro_stun_immune", False),
    }


def update_creep_ai_state(
    creep: Dict[str, Any],
    player_x: float,
    player_y: float,
    dt: float = 0.1
) -> Dict[str, Any]:
    """
    Volume VI, 6.1: State Machine AI Step:
    [SPAWN] -> [IDLE/PATROL] -> [CHASE] -> [ATTACK/CAST] -> [COOLDOWN]
    """
    if not creep.get("is_alive", True) or creep.get("hp", 0) <= 0:
        creep["ai_state"] = "DEAD"
        creep["is_alive"] = False
        return {"action": "none", "creep": creep}

    # Decrement cooldowns
    if creep.get("current_cooldown", 0.0) > 0.0:
        creep["current_cooldown"] = max(0.0, creep["current_cooldown"] - dt)
    if creep.get("ability_cooldown", 0.0) > 0.0:
        creep["ability_cooldown"] = max(0.0, creep["ability_cooldown"] - dt)

    dx = player_x - creep["x"]
    dy = player_y - creep["y"]
    dist = math.hypot(dx, dy)
    state = creep.get("ai_state", "SPAWN")
    action_event = "none"
    action_data = {}

    # State: SPAWN
    if state == "SPAWN":
        creep["spawn_timer"] = max(0.0, creep.get("spawn_timer", 0.5) - dt)
        if creep["spawn_timer"] <= 0.0:
            creep["ai_state"] = "IDLE"

    # State: IDLE / PATROL
    elif state == "IDLE":
        if dist <= AGGRO_RADIUS:
            creep["ai_state"] = "CHASE"

    # State: CHASE
    elif state == "CHASE":
        if dist > LEASH_RADIUS:
            creep["ai_state"] = "IDLE"
        else:
            # Special ability check (e.g. Centaur War Stomp)
            ability = creep.get("ability")
            if ability and creep.get("ability_cooldown", 0.0) <= 0.0:
                trig_dist = float(ability.get("trigger_distance") or ability.get("radius", 160))
                if dist <= trig_dist:
                    creep["ai_state"] = "CAST_ABILITY"
                    creep["ability_cooldown"] = float(ability.get("cooldown", 8.0))
                    action_event = "cast_ability"
                    action_data = {
                        "ability_id": ability.get("id"),
                        "ability_name": ability.get("name"),
                        "damage": ability.get("damage", 120),
                        "stun_duration": ability.get("stun_duration", 1.5)
                    }
                    return {"action": action_event, "data": action_data, "creep": creep}

            # Move towards player
            speed = float(creep.get("speed", 150))
            move_step = min(dist, speed * dt)
            role = creep.get("role")

            if role == "ranged":
                # Kite behavior: maintain 320px
                desired_dist = float(creep.get("attack_range", 320))
                if dist < desired_dist - 40:
                    # Move away
                    if dist > 0:
                        creep["x"] -= (dx / dist) * move_step
                        creep["y"] -= (dy / dist) * move_step
                elif dist > desired_dist + 40:
                    # Move closer
                    if dist > 0:
                        creep["x"] += (dx / dist) * move_step
                        creep["y"] += (dy / dist) * move_step
                else:
                    # Within ideal firing range
                    if creep.get("current_cooldown", 0.0) <= 0.0:
                        creep["ai_state"] = "ATTACK"
            else:
                # Melee / standard chase
                if dist <= creep.get("attack_range", 60):
                    if creep.get("current_cooldown", 0.0) <= 0.0:
                        creep["ai_state"] = "ATTACK"
                else:
                    if dist > 0:
                        creep["x"] += (dx / dist) * move_step
                        creep["y"] += (dy / dist) * move_step

    # State: ATTACK
    elif state == "ATTACK":
        action_event = "attack"
        action_data = {
            "damage": creep.get("effective_attack", creep.get("base_attack", 24)),
            "role": creep.get("role"),
            "projectile_speed": creep.get("projectile_speed", 0)
        }
        creep["current_cooldown"] = float(creep.get("attack_cooldown", 1.0))
        creep["ai_state"] = "COOLDOWN"

    # State: CAST_ABILITY
    elif state == "CAST_ABILITY":
        creep["ai_state"] = "COOLDOWN"

    # State: COOLDOWN
    elif state == "COOLDOWN":
        if creep.get("current_cooldown", 0.0) <= 0.0:
            if dist <= creep.get("attack_range", 60):
                creep["ai_state"] = "ATTACK"
            elif dist <= AGGRO_RADIUS:
                creep["ai_state"] = "CHASE"
            else:
                creep["ai_state"] = "IDLE"

    return {"action": action_event, "data": action_data, "creep": creep}


def apply_creep_auras(creeps_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Volume VI, 6.2: Neutral Alpha Wolf Pack Leader Aura (+30% attack damage to creeps).
    """
    has_alpha_wolf = any(
        c.get("is_alive", True) and c.get("type_id") == "alpha_wolf"
        for c in creeps_list
    )

    for c in creeps_list:
        base_atk = c.get("base_attack", 24)
        if has_alpha_wolf and c.get("is_alive", True):
            c["effective_attack"] = int(math.ceil(base_atk * 1.30))
            if "pack_leader" not in c.get("active_auras", []):
                c["active_auras"] = list(c.get("active_auras", [])) + ["pack_leader"]
        else:
            c["effective_attack"] = base_atk
            if "pack_leader" in c.get("active_auras", []):
                c["active_auras"] = [a for a in c.get("active_auras", []) if a != "pack_leader"]

    return creeps_list


def handle_creep_death(creep: Dict[str, Any]) -> Dict[str, Any]:
    """
    Volume VI, 6.2: Mud Golem death mechanic: splits into 2 small Shard Golems.
    """
    creep["is_alive"] = False
    creep["hp"] = 0
    creep["ai_state"] = "DEAD"

    on_death = creep.get("on_death")
    if on_death and on_death.get("action") == "split_into_shards":
        spawn_id = on_death.get("spawn_creep_id", "shard_golem")
        count = int(on_death.get("count", 2))
        x = creep.get("x", 0.0)
        y = creep.get("y", 0.0)

        spawned = []
        offsets = [(-25.0, 0.0), (25.0, 0.0)]
        for i in range(count):
            ox, oy = offsets[i % len(offsets)]
            sub = create_creep_instance(spawn_id, x=x + ox, y=y + oy)
            sub["ai_state"] = "CHASE"  # Immediately aggressive
            spawned.append(sub)

        return {
            "split": True,
            "spawned_creeps": spawned,
            "message": f"{creep['name']} распался на {count} малых големов!"
        }

    return {"split": False, "spawned_creeps": [], "message": f"{creep['name']} повержен."}
