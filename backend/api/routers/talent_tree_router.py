"""
API endpoints for the new hero talent tree system.
GET  /rpg/talents/tree       — returns current hero's talent tree with player's purchased nodes
POST /rpg/talents/tree/buy   — buys a talent node using talent_points
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud.rpg import (
    get_or_create_rpg_character,
    serialize_character_profile,
)
from backend.db.crud.rpg.talent_tree import (
    get_hero_tree,
    is_node_available,
    BRANCH_LABELS,
    TIER_UNLOCK_LEVEL,
    TIER_COST,
    get_hero_available_talent_points,
)

talent_tree_router = APIRouter(prefix="/rpg/talents", tags=["RPG Talents"])


@talent_tree_router.get("/tree")
async def get_talent_tree_endpoint(
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Returns current hero's talent tree with player's purchased nodes."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)

    hero_class = str(getattr(char, "hero_class", "pudge") or "pudge").lower()
    char_level = char.level or 1
    char_progress = char_level
    talent_points = get_hero_available_talent_points(char, hero_class)
    if getattr(char, "talent_points", None) != talent_points:
        char.talent_points = talent_points
        await session.commit()

    talents = getattr(char, "talents", {}) or {}
    purchased = (talents.get("tree") or {}).get(hero_class, {})

    hero_tree = get_hero_tree(hero_class)

    branches: Dict[str, list] = {b: [] for b in BRANCH_LABELS}
    for node_id, node_cfg in hero_tree.items():
        branch = node_cfg["branch"]
        tier = node_cfg["tier"]
        is_bought = bool(purchased.get(node_id, 0))
        can_buy = (
            not is_bought
            and talent_points >= node_cfg["cost"]
            and is_node_available(node_cfg, char_progress, purchased)
        )
        branches.setdefault(branch, []).append({
            "id": node_id,
            "tier": tier,
            "name": node_cfg["name"],
            "icon": node_cfg["icon"],
            "desc": node_cfg["desc"],
            "effect": node_cfg["effect"],
            "cost": node_cfg["cost"],
            "req": node_cfg.get("req"),
            "unlock_level": node_cfg["unlock_level"],
            "is_bought": is_bought,
            "can_buy": can_buy,
        })

    # Sort each branch by tier
    for b in branches:
        branches[b].sort(key=lambda n: n["tier"])

    return {
        "hero_class": hero_class,
        "char_level": char_level,
        "talent_points": talent_points,
        "purchased": purchased,
        "branches": branches,
        "branch_labels": BRANCH_LABELS,
        "tier_unlock_levels": TIER_UNLOCK_LEVEL,
    }


@talent_tree_router.post("/tree/buy")
async def buy_talent_node_endpoint(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Buys a talent tree node for the current hero using talent_points."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Герой natarGRP"
    node_id = str(payload.get("node_id", "")).strip()

    if not node_id:
        raise HTTPException(status_code=400, detail="Не указан node_id таланта.")

    char = await get_or_create_rpg_character(session, user_id=user_id)
    hero_class = str(getattr(char, "hero_class", "pudge") or "pudge").lower()
    char_level = char.level or 1
    char_progress = char_level
    talent_points = get_hero_available_talent_points(char, hero_class)

    hero_tree = get_hero_tree(hero_class)
    node_cfg = hero_tree.get(node_id)
    if not node_cfg:
        raise HTTPException(status_code=400, detail=f"Талант '{node_id}' не найден для героя {hero_class}.")

    talents = dict(getattr(char, "talents", {}) or {})
    tree = dict((talents.get("tree") or {}))
    hero_nodes = dict(tree.get(hero_class, {}))

    if hero_nodes.get(node_id):
        raise HTTPException(status_code=400, detail="Этот талант уже куплен!")

    req = node_cfg.get("req")
    if req and not hero_nodes.get(req):
        prev_name = hero_tree.get(req, {}).get("name", req)
        raise HTTPException(
            status_code=400,
            detail=f"Сначала изучите предыдущий талант ветки ({prev_name})."
        )

    if char_level < node_cfg["unlock_level"]:
        raise HTTPException(
            status_code=400,
            detail=f"Требуется {node_cfg['unlock_level']} уровень персонажа (у вас: {char_level})."
        )

    cost = node_cfg["cost"]
    if talent_points < cost:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно очков талантов! Нужно: {cost}, у вас: {talent_points}."
        )

    hero_nodes[node_id] = 1
    tree[hero_class] = hero_nodes
    talents["tree"] = tree
    char.talents = talents
    char.talent_points = max(0, talent_points - cost)
    flag_modified(char, "talents")
    await session.commit()
    await session.refresh(char)

    return {
        "success": True,
        "node_id": node_id,
        "node_name": node_cfg["name"],
        "talent_points_left": char.talent_points,
        "profile": serialize_character_profile(char, user_name=user_name),
    }
