"""
natarGRP Creeps Bestiary & 2D AI Router (Volume VI).
Provides endpoints for Dota 2 creeps catalog, 2D State Machine AI ticks, and death splits.
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Body

from backend.db.crud.rpg import (
    DOTA_BESTIARY_CATALOG,
    create_creep_instance,
    update_creep_ai_state,
    apply_creep_auras,
    handle_creep_death,
    AGGRO_RADIUS,
    LEASH_RADIUS,
)

creeps_bestiary_router = APIRouter(prefix="/rpg/creeps", tags=["rpg_creeps_bestiary"])


@creeps_bestiary_router.get("/bestiary")
async def get_creeps_bestiary_endpoint():
    """Returns catalog of Dota 2 creeps with behaviors, roles, stats, and auras."""
    return {
        "catalog": DOTA_BESTIARY_CATALOG,
        "aggro_radius": AGGRO_RADIUS,
        "leash_radius": LEASH_RADIUS,
        "total_creeps": len(DOTA_BESTIARY_CATALOG)
    }


@creeps_bestiary_router.post("/spawn")
async def spawn_creep_endpoint(payload: Dict[str, Any] = Body(default={})):
    """Spawns an instantiated creep with State Machine AI initialized."""
    creep_id = str(payload.get("type_id") or "melee_creep")
    x = float(payload.get("x") or 0.0)
    y = float(payload.get("y") or 0.0)
    instance = create_creep_instance(creep_id, x=x, y=y)
    return instance


@creeps_bestiary_router.post("/simulate_tick")
async def simulate_creeps_tick_endpoint(payload: Dict[str, Any] = Body(default={})):
    """
    Executes one 2D AI tick for a list of creeps:
    1. Evaluates pack auras (e.g. Alpha Wolf +30% attack).
    2. Runs State Machine step (Spawn -> Idle -> Chase -> Attack/Cast -> Cooldown).
    """
    raw_creeps = payload.get("creeps") or []
    player_x = float(payload.get("player_x") or 0.0)
    player_y = float(payload.get("player_y") or 0.0)
    dt = float(payload.get("dt") or 0.1)

    # 1. Apply auras
    creeps_with_auras = apply_creep_auras(raw_creeps)

    # 2. Step each creep AI
    updated_creeps = []
    actions_fired = []

    for c in creeps_with_auras:
        step_res = update_creep_ai_state(c, player_x=player_x, player_y=player_y, dt=dt)
        updated_creeps.append(step_res["creep"])
        if step_res["action"] != "none":
            actions_fired.append({
                "instance_id": c.get("instance_id"),
                "type_id": c.get("type_id"),
                "action": step_res["action"],
                "data": step_res.get("data", {})
            })

    return {
        "creeps": updated_creeps,
        "actions": actions_fired
    }


@creeps_bestiary_router.post("/split")
async def handle_creep_death_split_endpoint(payload: Dict[str, Any] = Body(default={})):
    """Executes on-death split mechanics (e.g. Mud Golem -> 2 Shard Golems)."""
    creep = payload.get("creep") or {}
    return handle_creep_death(creep)
