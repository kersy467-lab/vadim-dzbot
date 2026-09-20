import random
import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.config import settings
from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud.rpg import (
    NATAR_HEROES,
    DOTA_HEROES,
    get_or_create_rpg_character,
    serialize_character_profile,
    reset_rpg_character,
    upgrade_character_base_stat,
    open_wave_chest,
    calculate_xp_for_level,
    get_unlocked_features,
    get_full_progression_table,
    PROGRESSION_MILESTONES,
    LEVEL_CAP,
    STAT_POINTS_PER_LEVEL,
)
from backend.db.crud.rpg.talent_tree import (
    HERO_TALENT_TREE,
    BRANCH_LABELS,
    TIER_UNLOCK_LEVEL,
    TIER_COST,
    get_hero_tree,
    is_node_available,
)

rpg_router = APIRouter(prefix="/rpg", tags=["rpg"])


@rpg_router.get("/heroes")
async def get_dota_heroes_endpoint():
    """Returns list of all available natarGRP heroes."""
    return list(DOTA_HEROES.values())


@rpg_router.get("/heroes/detailed")
async def get_all_heroes_detailed_endpoint():
    """Returns complete catalog of all 8 Dota 2 heroes with skills, stat gains and talents."""
    result = []
    for h_id, hero in DOTA_HEROES.items():
        result.append({
            "id": h_id,
            "name": hero.get("name"),
            "icon": hero.get("icon"),
            "avatar": hero.get("avatar"),
            "attr": hero.get("attr"),
            "desc": hero.get("desc"),
            "base_hp": hero.get("base_hp"),
            "base_mp": hero.get("base_mp"),
            "base_speed": hero.get("base_speed", 200),
            "base_armor": hero.get("base_armor", 3.0),
            "str": hero.get("str"),
            "agi": hero.get("agi"),
            "int": hero.get("int"),
            "str_gain": hero.get("str_gain", 2.0),
            "agi_gain": hero.get("agi_gain", 2.0),
            "int_gain": hero.get("int_gain", 2.0),
            "skills": hero.get("skills", []),
            "talents": hero.get("talents", {}),
            "starter_weapon": hero.get("starter_weapon"),
            "starter_armor": hero.get("starter_armor"),
        })
    return result


@rpg_router.get("/heroes/{hero_id}")
async def get_hero_by_id_endpoint(hero_id: str):
    """Returns detailed specification for a specific Dota 2 hero."""
    h_norm = hero_id.strip().lower()
    hero = DOTA_HEROES.get(h_norm)
    if not hero:
        raise HTTPException(status_code=404, detail=f"Герой '{hero_id}' не найден в ростере.")
    return {
        "id": h_norm,
        "name": hero.get("name"),
        "icon": hero.get("icon"),
        "avatar": hero.get("avatar"),
        "attr": hero.get("attr"),
        "desc": hero.get("desc"),
        "base_hp": hero.get("base_hp"),
        "base_mp": hero.get("base_mp"),
        "base_speed": hero.get("base_speed", 200),
        "base_armor": hero.get("base_armor", 3.0),
        "str": hero.get("str"),
        "agi": hero.get("agi"),
        "int": hero.get("int"),
        "str_gain": hero.get("str_gain", 2.0),
        "agi_gain": hero.get("agi_gain", 2.0),
        "int_gain": hero.get("int_gain", 2.0),
        "skills": hero.get("skills", []),
        "talents": hero.get("talents", {}),
        "starter_weapon": hero.get("starter_weapon"),
        "starter_armor": hero.get("starter_armor"),
    }


@rpg_router.get("/progression/table")
async def get_progression_table_endpoint():
    """Returns level 1 to 50 progression model with XP formulas and milestones."""
    return {"level_cap": LEVEL_CAP, "stat_points_per_level": STAT_POINTS_PER_LEVEL, "table": get_full_progression_table()}


@rpg_router.get("/progression/milestones")
async def get_milestones_endpoint():
    """Returns list of key level milestones (pets, forge, relics, ultimate, rebirth)."""
    return PROGRESSION_MILESTONES


@rpg_router.get("/progression/unlocked")
async def get_my_unlocked_features_endpoint(
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Returns unlocked game systems for current character level."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)
    return {
        "level": char.level,
        "unlocked_features": get_unlocked_features(char.level),
        "xp_needed": calculate_xp_for_level(char.level),
        "current_xp": char.xp,
        "stat_points": getattr(char, "stat_points", 0),
    }


@rpg_router.post("/chest/open")
async def open_chest_endpoint(
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Opens a reward chest earned every 10-20 waves."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Герой natarGRP"

    char = await get_or_create_rpg_character(session, user_id=user_id)
    wave = payload.get("wave", char.dungeon_cleared)
    
    if wave > char.dungeon_cleared:
        raise HTTPException(status_code=400, detail="Эта волна еще не пройдена!")
        
    talents = dict(char.talents or {})
    last_chest_wave = talents.get("_last_chest_wave", 0)
    
    if wave <= last_chest_wave:
        raise HTTPException(status_code=400, detail="Сундук за эту волну уже открыт!")
        
    res = await open_wave_chest(session, char, wave)
    
    talents["_last_chest_wave"] = wave
    char.talents = talents
    flag_modified(char, "talents")
    
    res["profile"] = serialize_character_profile(char, user_name=user_name)
    return res


@rpg_router.get("/profile")
async def get_rpg_profile_endpoint(
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Returns or initializes the RPG Character profile for the current user."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Дотер 11 «Б»"

    char = await get_or_create_rpg_character(session, user_id=user_id)
    prof = serialize_character_profile(char, user_name=user_name)
    prof["is_admin"] = bool(user and (user.role == "admin" or user.tg_id == settings.ADMIN_ID or user.tg_id == 1053722876))
    prof["tg_id"] = user.tg_id if user else None
    return prof


@rpg_router.post("/class/select")
async def select_hero_class_endpoint(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Selects or changes Dota 2 hero (Pudge, Jugg, PA, SF, Invoker, WK, AM, Leshrac)."""
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Дотер 11 «Б»"

    hero_id = payload.get("hero_class", "pudge").strip().lower()
    if hero_id not in DOTA_HEROES:
        raise HTTPException(status_code=400, detail="Неизвестный герой Dota 2")

    char = await get_or_create_rpg_character(session, user_id=user_id)
    cfg = DOTA_HEROES[hero_id]

    char.hero_class = hero_id
    char.strength = cfg["str"]
    char.agility = cfg["agi"]
    char.intelligence = cfg["int"]
    char.vitality = cfg.get("vit", cfg["str"])

    starter_w = dict(cfg.get("starter_weapon", {}))
    if starter_w:
        starter_w["uid"] = f"w_{hero_id[:4]}_{str(uuid.uuid4())[:6]}"
        starter_w["slot"] = "slot_1"
        
    starter_a = dict(cfg.get("starter_armor", {}))
    if starter_a:
        starter_a["uid"] = f"a_{hero_id[:4]}_{str(uuid.uuid4())[:6]}"
        starter_a["slot"] = "slot_2"

    eq = dict(char.equipment or {})
    # Only provide starter items if character has no gear equipped
    if not any(eq.values()):
        if starter_w:
            eq["slot_1"] = starter_w
        if starter_a:
            eq["slot_2"] = starter_a
        char.equipment = eq
        flag_modified(char, "equipment")

    from backend.db.crud.rpg.talent_tree import get_hero_available_talent_points
    char.talent_points = get_hero_available_talent_points(char, hero_id)

    await session.commit()
    await session.refresh(char)
    return serialize_character_profile(char, user_name=user_name)


@rpg_router.post("/upgrade/stat")
async def upgrade_stat_endpoint(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Upgrades Strength, Agility, Intelligence using free stat points or farmed gold."""
    user_id = user.id if user else 1
    stat_name = payload.get("stat", "").strip().lower()
    amount = payload.get("amount", 1)

    char = await get_or_create_rpg_character(session, user_id=user_id)
    ok, msg = await upgrade_character_base_stat(session, char, stat_name, amount=amount)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    user_name = user.display_name if user else "Дотер 11 «Б»"
    return {
        "success": True,
        "message": msg,
        "profile": serialize_character_profile(char, user_name=user_name)
    }


@rpg_router.post("/reset")
async def reset_character_endpoint(
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Hardcore Reset: Resets RPG character to level 1 for a fresh grind."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)
    ok, msg = await reset_rpg_character(session, char)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    user_name = user.display_name if user else "Дотер 11 «Б»"
    return {
        "success": True,
        "message": msg,
        "profile": serialize_character_profile(char, user_name=user_name)
    }


@rpg_router.post("/talents/upgrade")
async def upgrade_talent_endpoint(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Герой natarGRP"
    char = await get_or_create_rpg_character(session, user_id=user_id)
    talent_id = payload.get("talent_id")
    if not talent_id or talent_id not in {"lifesteal", "crit_mult", "cooldown", "dodge"}:
        raise HTTPException(status_code=400, detail="Неизвестный талант")
    if char.talent_points <= 0:
        raise HTTPException(status_code=400, detail="Нет очков талантов!")
    talents = dict(char.talents or {})
    current_lvl = talents.get(talent_id, 0)
    if current_lvl >= 5:
        raise HTTPException(status_code=400, detail="Талант максимального уровня!")
    talents[talent_id] = current_lvl + 1
    char.talents = talents
    char.talent_points -= 1
    flag_modified(char, "talents")
    await session.commit()
    return {"status": "ok", "profile": serialize_character_profile(char, user_name=user_name)}


@rpg_router.post("/talents/choose")
async def choose_dota_talent_endpoint(
    payload: Dict[str, Any] = Body(...),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Selects Left or Right talent for a given tier (10, 15, 20, 25)."""
    user_id = user.id if user else 1
    char = await get_or_create_rpg_character(session, user_id=user_id)
    try:
        tier = int(payload.get("tier", 0))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid tier")
    choice = str(payload.get("choice", "")).strip().lower()
    if tier not in [10, 15, 20, 25]:
        raise HTTPException(status_code=400, detail="Тир таланта должен быть 10, 15, 20 или 25.")
    if choice not in ["left", "right"]:
        raise HTTPException(status_code=400, detail="Выбор должен быть 'left' или 'right'.")
    if char.level < tier:
        raise HTTPException(status_code=400, detail=f"Требуется {tier} уровень персонажа (у вас {char.level}).")

    talents = dict(char.talents or {})
    dota_talents = dict(talents.get("dota_talents") or {})
    dota_talents[str(tier)] = choice
    talents["dota_talents"] = dota_talents
    char.talents = talents
    flag_modified(char, "talents")
    await session.commit()
    await session.refresh(char)

    user_name = user.display_name if user else "Герой natarGRP"
    return {
        "success": True,
        "tier": tier,
        "choice": choice,
        "profile": serialize_character_profile(char, user_name=user_name)
    }
