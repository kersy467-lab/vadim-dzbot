import random
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud.rpg import (
    get_or_create_rpg_character,
    serialize_character_profile,
    add_xp_and_gold_to_character,
    get_rpg_leaderboard_data,
    open_wave_chest,
    open_boss_raid_chest,
    run_dungeon_wave,
    BOSS_DIFFICULTIES,
    DOTA_BOSS_CATALOG,
    calculate_boss_dynamic_damage,
    calculate_enrage_multiplier,
    get_boss_phase_state,
)
from backend.api.game_rooms import game_manager, RAID_BOSSES
from backend.api.routers.heroes_dota import rpg_router

KILL_STREAK_TITLES = [
    "KILLING SPREE! ⚡",
    "DOMINATING! 🔥",
    "MEGA KILL! 💥",
    "UNSTOPPABLE! ⚔️",
    "WICKED SICK! ☠️",
    "MONSTER KILL! 👹",
    "GODLIKE! 👑",
    "HOLY SHIT! 🌟",
    "RAMPAGE! 🏆"
]

FLOOR_BOSS_ORDER = [
    "golem", "lich", "tormentor", "dragon", "pudge_boss",
    "faceless_void", "roshan", "tidehunter", "sf_boss", "necrophos",
    "terrorblade", "invoker_boss", "chaos_knight", "dark_tormentor", 
    "storm_spirit", "doom"
]


@rpg_router.post("/dungeon/wave")
async def slash_creep_wave_endpoint(
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Бесконечное месилово крипов!
    Герой сражается с волной крипов или боссом этажа на текущем уровне подземелья.
    """
    user_id = user.id if user else 1
    user_name = user.display_name if user else "Дотер 11 «Б»"

    char = await get_or_create_rpg_character(session, user_id=user_id)

    # Raid Boss Action Defeat
    if payload.get("is_raid_boss"):
        boss_id = str(payload.get("boss_id") or "golem").strip().lower()
        boss_tmpl = RAID_BOSSES.get(boss_id, RAID_BOSSES["golem"])
        gold_earned = int(payload.get("earned_gold") or boss_tmpl.get("gold_reward", 600))
        xp_earned = int(payload.get("earned_xp") or boss_tmpl.get("xp_reward", 400))
        char.boss_kills = getattr(char, "boss_kills", 0) + 1
        leveled_up, new_lvl = await add_xp_and_gold_to_character(session, char, xp_earned, gold_earned)
        chest_reward = await open_boss_raid_chest(session, char, boss_id=boss_id)
        await session.commit()
        await session.refresh(char)
        return {
            "victory": True,
            "is_raid_boss": True,
            "boss_name": boss_tmpl.get("name"),
            "gold_earned": gold_earned,
            "gold_reward": gold_earned,
            "xp_earned": xp_earned,
            "xp_reward": xp_earned,
            "leveled_up": leveled_up,
            "chest_reward": chest_reward,
            "profile": serialize_character_profile(char, user_name=user_name)
        }

    # Direct sync from Action Arena (real-time combat)
    direct_gold = payload.get("earned_gold")
    direct_xp = payload.get("earned_xp")
    direct_wave = payload.get("wave_cleared")
    if direct_gold is not None or direct_xp is not None or direct_wave is not None:
        gold_earned = min(int(direct_gold or 0), 1000000)
        xp_earned = min(int(direct_xp or 0), 1000000)
        if direct_wave:
            claimed_wave = int(direct_wave)
            if claimed_wave > char.dungeon_cleared + 1:
                claimed_wave = char.dungeon_cleared + 1
            char.dungeon_cleared = max(char.dungeon_cleared, claimed_wave)
        else:
            char.dungeon_cleared += 1
        char.dungeon_floor = (char.dungeon_cleared // 20) + 1
        leveled_up, new_lvl = await add_xp_and_gold_to_character(session, char, xp_earned, gold_earned)

        chest_reward = None
        if char.dungeon_cleared % 10 == 0:
            if char.dungeon_cleared % 20 == 0:
                f_idx = (char.dungeon_cleared // 20) - 1
                cur_boss_id = FLOOR_BOSS_ORDER[min(len(FLOOR_BOSS_ORDER) - 1, max(0, f_idx))]
                chest_reward = await open_boss_raid_chest(session, char, boss_id=cur_boss_id)
            else:
                chest_reward = await open_wave_chest(session, char, char.dungeon_cleared)

        await session.commit()
        await session.refresh(char)

        style_rank = str(payload.get("style_rank") or "D").upper()
        combo_max = int(payload.get("combo_max") or 0)
        return {
            "victory": True,
            "wave_cleared": char.dungeon_cleared,
            "floor": char.dungeon_floor,
            "gold_earned": gold_earned,
            "xp_earned": xp_earned,
            "style_rank": style_rank,
            "combo_max": combo_max,
            "leveled_up": leveled_up,
            "chest_reward": chest_reward,
            "profile": serialize_character_profile(char, user_name=user_name)
        }

    # Standard simulated dungeon combat via modular dungeon runner
    return await run_dungeon_wave(session, char, user_name=user_name)


@rpg_router.get("/bosses")
async def get_coop_bosses_endpoint():
    """Returns list of Raid Bosses for Co-op battles (Рошан, Терзатель, Древний Дракон)."""
    return list(RAID_BOSSES.values())


@rpg_router.get("/bosses/dynamic")
async def get_dynamic_bosses_catalog():
    """
    Returns dynamic raid bosses catalog with phase rules, telegraph attacks,
    and difficulty multipliers (Volume VII).
    """
    return {
        "bosses": DOTA_BOSS_CATALOG,
        "difficulties": BOSS_DIFFICULTIES,
        "phases": [
            {
                "phase": 1,
                "hp_range": "100% - 70%",
                "damage_mult": 1.0,
                "shield": "0%",
                "description": "Базовый натиск круговыми пулями"
            },
            {
                "phase": 2,
                "hp_range": "70% - 30%",
                "damage_mult": 1.25,
                "shield": "25%",
                "description": "Элементальный щит (поглощает 25% урона) и призыв прислужников"
            },
            {
                "phase": 3,
                "hp_range": "< 30%",
                "damage_mult": 1.55,
                "shield": "0%",
                "description": "Отчаянное Безумие: +50% скорости атак, огненные следы на арене"
            }
        ],
        "enrage_rule": "Каждые 8 секунд боя босс получает +1 стак Enrage (+14% урона). Созвездие Укротителя замедляет набор на 14% за уровень."
    }


@rpg_router.post("/bosses/simulate_damage")
async def simulate_boss_damage_endpoint(payload: Dict[str, Any] = Body(default={})):
    """
    Calculates dynamic boss damage based on Volume VII, 7.1:
    Damage = [BaseAtk * M_difficulty * M_enrage(t) * M_party * M_phase] - Defense
    """
    boss_id = str(payload.get("boss_id") or "roshan").strip().lower()
    boss_tmpl = DOTA_BOSS_CATALOG.get(boss_id) or RAID_BOSSES.get(boss_id, {})
    base_atk = int(payload.get("base_atk") or boss_tmpl.get("base_atk") or boss_tmpl.get("atk_min", 850))
    difficulty = str(payload.get("difficulty") or "normal").strip().lower()
    elapsed_seconds = float(payload.get("elapsed_seconds") or 0.0)
    current_hp = int(payload.get("current_hp") or boss_tmpl.get("base_hp") or boss_tmpl.get("max_hp", 2_800_000))
    max_hp = int(payload.get("max_hp") or boss_tmpl.get("base_hp") or boss_tmpl.get("max_hp", 2_800_000))
    party_size = max(1, int(payload.get("party_size") or 1))
    target_defense = max(0, int(payload.get("target_defense") or 0))
    pacifier_level = max(0, int(payload.get("pacifier_level") or 0))

    damage = calculate_boss_dynamic_damage(
        base_atk=base_atk,
        difficulty=difficulty,
        elapsed_seconds=elapsed_seconds,
        current_hp=current_hp,
        max_hp=max_hp,
        party_size=party_size,
        target_defense=target_defense,
        pacifier_level=pacifier_level
    )

    phase_info = get_boss_phase_state(current_hp, max_hp)
    enrage_mult = calculate_enrage_multiplier(elapsed_seconds, pacifier_level=pacifier_level)
    diff_info = BOSS_DIFFICULTIES.get(difficulty, BOSS_DIFFICULTIES["normal"])

    return {
        "boss_id": boss_id,
        "damage": damage,
        "base_atk": base_atk,
        "difficulty": difficulty,
        "difficulty_mult": diff_info["atk_mult"],
        "enrage_mult": enrage_mult,
        "elapsed_seconds": elapsed_seconds,
        "enrage_stacks": int(elapsed_seconds // 8),
        "party_size": party_size,
        "party_mult": 1.0 + (party_size - 1) * 0.25,
        "phase": phase_info,
        "target_defense": target_defense
    }


@rpg_router.get("/leaderboard")
async def get_rpg_leaderboard_endpoint(session: AsyncSession = Depends(get_db_session)):
    """Returns the class leaderboard for Dota 2 heroes."""
    return await get_rpg_leaderboard_data(session)


@rpg_router.post("/room/{room_id}/sync")
async def sync_rpg_room_character(
    room_id: str,
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Loads current hero stats and Dota items directly into active PvP or Co-op room."""
    room = game_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    user_id = user.id if user else 1
    user_name = user.display_name if user else "Дотер"
    user_tg_id = user.tg_id if user else 0

    role = room.get_player_role(user_tg_id)
    if not role:
        return room.to_dict(viewer_tg_id=user_tg_id)

    char = await get_or_create_rpg_character(session, user_id=user_id)
    prof = serialize_character_profile(char, user_name=user_name)

    if hasattr(room, "sync_character_data"):
        room.sync_character_data(role, prof)

    return room.to_dict(viewer_tg_id=user_tg_id)
