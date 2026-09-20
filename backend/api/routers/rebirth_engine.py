from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud.rpg import (
    get_or_create_rpg_character,
    serialize_character_profile,
    calculate_rebirth_multiplier,
    get_rebirth_rank_info,
    perform_ascension,
    upgrade_constellation,
    CONSTELLATIONS_CATALOG,
    MAX_REBIRTH_RANK,
)

rebirth_engine_router = APIRouter(prefix="/rpg/rebirth_system", tags=["RPG Rebirth"])


@rebirth_engine_router.get("/info")
async def get_rebirth_info_endpoint(
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Returns current character rebirth rank, stat multiplier and ascension status."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)
    
    current_rank = getattr(char, "rebirths", 0)
    rank_info = get_rebirth_rank_info(current_rank)
    
    req_level = rank_info["next_min_level"]
    can_ascend = bool(req_level and char.level >= req_level and current_rank < MAX_REBIRTH_RANK)
    
    talents = getattr(char, "talents", {}) or {}
    essence = talents.get("rebirth_essence", 0)
    
    return {
        "current_level": char.level,
        "current_rank": current_rank,
        "max_rank": MAX_REBIRTH_RANK,
        "title": rank_info["title"],
        "multiplier": rank_info["multiplier"],
        "multiplier_pct": rank_info["multiplier_pct"],
        "astral_essence": essence,
        "can_ascend": can_ascend,
        "next_rank": rank_info["next_rank"],
        "next_min_level": req_level,
        "next_essence_reward": rank_info["next_essence_reward"],
    }


@rebirth_engine_router.post("/ascend")
@rebirth_engine_router.post("/")
async def perform_rebirth_endpoint(
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Performs character ascension to the next rebirth rank."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Герой natarGRP"
    char = await get_or_create_rpg_character(session, user_id=user_id)

    ok, msg, details = await perform_ascension(session, char)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg,
        "details": details,
        "profile": serialize_character_profile(char, user_name=user_name),
    }


@rebirth_engine_router.get("/constellations")
async def get_constellations_endpoint(
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Returns catalog of the 6 Astral Constellations and character's current ranks."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)

    talents = getattr(char, "talents", {}) or {}
    essence = talents.get("rebirth_essence", 0)
    constellations = talents.get("constellations", {}) or {}

    nodes = []
    for c_id, c_cfg in CONSTELLATIONS_CATALOG.items():
        lvl = constellations.get(c_id, 0)
        max_l = c_cfg["max_level"]
        nodes.append({
            "id": c_id,
            "name": c_cfg["name"],
            "icon": c_cfg["icon"],
            "desc": c_cfg["desc"],
            "current_level": lvl,
            "max_level": max_l,
            "is_max": lvl >= max_l,
            "cost_essence": c_cfg["cost_per_level"] if lvl < max_l else 0,
            "bonus_per_level": c_cfg["bonus_per_level"],
        })

    return {
        "astral_essence": essence,
        "constellations": nodes,
    }


@rebirth_engine_router.post("/constellations/upgrade")
async def upgrade_constellation_endpoint(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Upgrades a constellation node using 1 Astral Essence."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Герой natarGRP"
    constellation_id = payload.get("constellation_id", "").strip()

    if not constellation_id:
        raise HTTPException(status_code=400, detail="Не указан ID созвездия.")

    char = await get_or_create_rpg_character(session, user_id=user_id)
    ok, msg, details = await upgrade_constellation(session, char, constellation_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "success": True,
        "message": msg,
        "details": details,
        "profile": serialize_character_profile(char, user_name=user_name),
    }