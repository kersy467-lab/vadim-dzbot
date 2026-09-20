import random
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud.rpg import get_or_create_rpg_character, serialize_character_profile
from backend.db.crud.rpg.pets_config import (
    PETS_CATALOG,
    PET_HATCH_RATES,
    MAX_PET_STARS,
    MERGE_COST_GEMS,
    HATCH_COST_GEMS,
)

pets_system_router = APIRouter(prefix="/rpg/pets", tags=["RPG Pets"])


@pets_system_router.get("/catalog")
async def get_pets_catalog_endpoint():
    """Returns catalog of all 6 companion pets, their abilities, and hatch rates."""
    return {
        "pets": list(PETS_CATALOG.values()),
        "hatch_rates": PET_HATCH_RATES,
        "hatch_cost_gems": HATCH_COST_GEMS,
        "merge_cost_gems": MERGE_COST_GEMS,
        "max_stars": MAX_PET_STARS,
    }


@pets_system_router.post("/hatch")
async def hatch_pet(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Hatch a random pet for 50 gems."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Дотер 11 «Б»"
    char = await get_or_create_rpg_character(session, user_id=user_id)

    if getattr(char, "gems", 0) < HATCH_COST_GEMS:
        raise HTTPException(status_code=400, detail="Недостаточно самоцветов (нужно 50 💎).")

    char.gems -= HATCH_COST_GEMS

    # Roll rarity across 6 tiers
    roll = random.uniform(0, 100)
    cumulative = 0
    selected_rarity = "common"

    rates = [
        ("immortal", PET_HATCH_RATES["immortal"]),
        ("mythic", PET_HATCH_RATES["mythic"]),
        ("legendary", PET_HATCH_RATES["legendary"]),
        ("epic", PET_HATCH_RATES["epic"]),
        ("rare", PET_HATCH_RATES["rare"]),
        ("common", PET_HATCH_RATES["common"]),
    ]

    for rarity, prob in rates:
        cumulative += prob
        if roll <= cumulative:
            selected_rarity = rarity
            break

    # Filter pets by rarity
    possible_pets = [p for p in PETS_CATALOG.values() if p["rarity"] == selected_rarity]
    if not possible_pets:
        possible_pets = list(PETS_CATALOG.values())

    pet_cfg = random.choice(possible_pets)
    
    new_pet = {
        "uid": str(uuid.uuid4()),
        "type": pet_cfg["id"],
        "stars": 1,
        "is_equipped": False
    }

    pets = list(getattr(char, "pets", []) or [])
    pets.append(new_pet)
    char.pets = pets
    flag_modified(char, "pets")

    await session.commit()
    await session.refresh(char)

    return {
        "success": True,
        "pet": new_pet,
        "pet_cfg": pet_cfg,
        "profile": serialize_character_profile(char)
    }


@pets_system_router.post("/equip")
async def equip_pet(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Equips or unequips a pet."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)
    pet_uid = payload.get("pet_uid")
    
    pets = list(getattr(char, "pets", []) or [])
    found = False
    
    for p in pets:
        if p["uid"] == pet_uid:
            p["is_equipped"] = True
            found = True
        else:
            p["is_equipped"] = False  # Only 1 pet equipped at a time

    if not found:
        raise HTTPException(status_code=400, detail="Питомец не найден.")

    char.pets = pets
    flag_modified(char, "pets")
    await session.commit()
    await session.refresh(char)

    return {
        "success": True,
        "profile": serialize_character_profile(char)
    }


@pets_system_router.post("/upgrade")
async def upgrade_pet(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Merges 3 identical pets of the same stars to create a higher star pet (up to 5★)."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Дотер 11 «Б»"
    char = await get_or_create_rpg_character(session, user_id=user_id)
    pet_uid = payload.get("pet_uid")

    if getattr(char, "gems", 0) < MERGE_COST_GEMS:
        raise HTTPException(status_code=400, detail=f"Нужно {MERGE_COST_GEMS} 💎 для ритуала слияния!")

    pets = list(getattr(char, "pets", []) or [])
    target_pet = next((p for p in pets if p["uid"] == pet_uid), None)
    if not target_pet:
        raise HTTPException(status_code=400, detail="Питомец не найден.")

    pet_type = target_pet["type"]
    pet_stars = target_pet.get("stars", 1)

    if pet_stars >= MAX_PET_STARS:
        raise HTTPException(status_code=400, detail=f"Питомец уже достиг максимального ранга {MAX_PET_STARS}★!")

    # Find 3 pets of same type and stars (including target)
    matching_uids = [p["uid"] for p in pets if p["type"] == pet_type and p.get("stars", 1) == pet_stars]
    if len(matching_uids) < 3:
        raise HTTPException(status_code=400, detail="Нужно 3 одинаковых питомца одной звёздности для слияния!")

    char.gems -= MERGE_COST_GEMS
    uids_to_consume = [uid for uid in matching_uids if uid != pet_uid][:2]  # Consume 2 duplicates

    new_pets = [p for p in pets if p["uid"] not in uids_to_consume]
    for p in new_pets:
        if p["uid"] == pet_uid:
            p["stars"] = pet_stars + 1
            break

    char.pets = new_pets
    flag_modified(char, "pets")

    await session.commit()
    await session.refresh(char)

    pet_cfg = PETS_CATALOG.get(pet_type, {})
    return {
        "success": True,
        "message": f"✨ Слияние 3-в-1 успешно! «{pet_cfg.get('name', 'Питомец')}» теперь {pet_stars + 1}★!",
        "stars": pet_stars + 1,
        "profile": serialize_character_profile(char, user_name=user_name)
    }
