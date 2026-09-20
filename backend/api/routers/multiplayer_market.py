"""
natarGRP Multiplayer & Marketplace Router — Threat Engine, Party Synergies,
World Titan Roshan (50M HP) and P2P Auction (Volume IX).
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud.rpg import (
    get_or_create_rpg_character,
    calculate_player_threat,
    determine_boss_target,
    calculate_party_synergies,
    get_world_boss_status,
    record_world_boss_attack,
    reset_world_boss,
    get_market_listings,
    list_item_for_sale,
    cancel_market_listing,
    buy_market_item,
    MARKET_FEE_PCT,
)

multiplayer_market_router = APIRouter(prefix="/rpg", tags=["rpg_multiplayer_market"])


# --- 9.1 & 9.2: Threat Engine & Party Synergies ---

@multiplayer_market_router.get("/multiplayer/synergies")
async def get_party_synergies_endpoint(
    classes: str = Query(..., description="Comma-separated hero classes, e.g. 'pudge,juggernaut,invoker'")
):
    """Calculates active team synergies for given party composition."""
    hero_list = [c.strip().lower() for c in classes.split(",") if c.strip()]
    return calculate_party_synergies(hero_list)


@multiplayer_market_router.post("/multiplayer/threat/calculate")
async def calculate_threat_endpoint(payload: Dict[str, Any] = Body(default={})):
    """
    Volume IX, 9.1: Threat Engine calculation.
    Supports either single player calculation or full party target resolution.
    """
    players_data = payload.get("players")
    if players_data and isinstance(players_data, dict):
        threat_map = {}
        for pid, pdata in players_data.items():
            dmg = float(pdata.get("damage_dealt", 0.0))
            taunt = float(pdata.get("taunt_mult", 1.0))
            dist = float(pdata.get("distance", 200.0))
            heal = float(pdata.get("heal_provided", 0.0))
            threat_map[pid] = calculate_player_threat(dmg, taunt, dist, heal)
        target = determine_boss_target(threat_map)
        return {
            "threats": threat_map,
            "target_player_id": target
        }

    # Single player threat calculation
    dmg = float(payload.get("damage_dealt", 0.0))
    taunt = float(payload.get("taunt_mult", 1.0))
    dist = float(payload.get("distance", 200.0))
    heal = float(payload.get("heal_provided", 0.0))
    threat_val = calculate_player_threat(dmg, taunt, dist, heal)
    return {"threat": threat_val}


# --- 9.3: Мировой Рошан (World Titan Roshan — 50M HP) ---

@multiplayer_market_router.get("/world_boss/status")
async def get_world_boss_status_endpoint():
    """Returns status, HP percentage and leaderboard of World Titan Roshan."""
    return get_world_boss_status()


@multiplayer_market_router.post("/world_boss/attack")
async def attack_world_boss_endpoint(
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Deals attack damage to World Titan Roshan and updates server raid stats."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Дотер 11 «Б»"
    char = await get_or_create_rpg_character(session, user_id=user_id)

    dmg = int(payload.get("damage") or 1000)
    result = record_world_boss_attack(user_id=char.user_id, user_name=user_name, damage=dmg)
    return result


@multiplayer_market_router.post("/world_boss/reset")
async def reset_world_boss_endpoint():
    """Resets World Titan Roshan (for admin/testing purposes)."""
    return reset_world_boss()


# --- 9.4: P2P Торговая Площадка (Marketplace) ---

@multiplayer_market_router.get("/market/listings")
async def get_market_listings_endpoint(
    rarity: Optional[str] = Query(None),
    slot: Optional[str] = Query(None),
    currency: Optional[str] = Query(None)
):
    """Returns active marketplace listings with optional filters."""
    listings = get_market_listings(rarity=rarity, slot=slot, currency=currency)
    return {
        "listings": listings,
        "fee_pct": MARKET_FEE_PCT,
        "total": len(listings)
    }


@multiplayer_market_router.post("/market/list")
async def list_market_item_endpoint(
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Puts an item from player's inventory up for sale."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Торговец"
    char = await get_or_create_rpg_character(session, user_id=user_id)

    item_uid = str(payload.get("item_uid") or "")
    price = int(payload.get("price") or 0)
    currency = str(payload.get("currency") or "gold")

    try:
        return await list_item_for_sale(
            session=session,
            char=char,
            item_uid=item_uid,
            price=price,
            currency=currency,
            user_name=user_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@multiplayer_market_router.post("/market/buy")
async def buy_market_item_endpoint(
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Purchases an item listed on the marketplace."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)

    listing_id = str(payload.get("listing_id") or "")
    try:
        return await buy_market_item(session=session, buyer_char=char, listing_id=listing_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@multiplayer_market_router.post("/market/cancel")
async def cancel_market_listing_endpoint(
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Cancels a player's active listing and returns the item to inventory."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)

    listing_id = str(payload.get("listing_id") or "")
    try:
        return await cancel_market_listing(session=session, char=char, listing_id=listing_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
