import random
import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from backend.db.models import RPGCharacter, User
from backend.db.crud.rpg.heroes import NATAR_HEROES
from backend.db.crud.rpg.items_catalog import RARITY_MULTIPLIERS
from backend.db.crud.rpg.character_stats import calculate_character_effective_stats
from backend.db.crud.rpg.progression_math import (
    calculate_xp_for_level,
    get_unlocked_features,
    LEVEL_CAP,
    STAT_POINTS_PER_LEVEL
)

# ==============================================================================
# CHARACTER CALCULATIONS & CRUDS
# ==============================================================================



# ==============================================================================
# CHARACTER CALCULATIONS & CRUDS
# ==============================================================================

async def get_or_create_rpg_character(
    session: AsyncSession,
    user_id: int,
    preferred_class: str = "pudge"
) -> RPGCharacter:
    """Gets existing character or creates a new one with chosen hero archetype."""
    user_check = await session.execute(select(User).where(User.id == user_id))
    user_record = user_check.scalar_one_or_none()
    if not user_record:
        fallback_tg = 999990000 + user_id
        tg_check = await session.execute(select(User).where(User.tg_id == fallback_tg))
        user_record = tg_check.scalar_one_or_none()
        if not user_record:
            user_record = User(tg_id=fallback_tg, full_name="Герой natarGRP", role="student")
            session.add(user_record)
            await session.commit()
            await session.refresh(user_record)
        user_id = user_record.id

    res = await session.execute(select(RPGCharacter).where(RPGCharacter.user_id == user_id))
    char = res.scalar_one_or_none()

    if not char:
        hero_cfg = NATAR_HEROES.get(preferred_class, NATAR_HEROES["pudge"])
        starter_weapon = dict(hero_cfg["starter_weapon"])
        starter_weapon["uid"] = str(uuid.uuid4())[:8]
        starter_weapon["slot"] = "slot_1"
        starter_armor = dict(hero_cfg["starter_armor"])
        starter_armor["uid"] = str(uuid.uuid4())[:8]
        starter_armor["slot"] = "slot_5"

        starter_potion = {
            "uid": str(uuid.uuid4())[:8],
            "name": "Зелье Исцеления",
            "type": "potion",
            "slot": "consumable",
            "slot_name": "Зелье",
            "slot_icon": "🧪",
            "rarity": "common",
            "rarity_name": "Обычный",
            "rarity_color": "#94a3b8",
            "icon": "🧴",
            "heal_amount": 120,
            "count": 3,
            "bonus_desc": "❤️ Восстанавливает 120 HP (3 шт.)"
        }

        starter_relic = {
            "uid": str(uuid.uuid4())[:8],
            "name": "Талисман Энергии",
            "type": "relic",
            "slot": "slot_2",
            "slot_name": "Реликвия",
            "slot_icon": "💍",
            "rarity": "common",
            "rarity_name": "Обычный",
            "rarity_color": "#94a3b8",
            "icon": "🌿",
            "upgrade": 0,
            "bonus": {"hp": 50, "mp": 40},
            "bonus_desc": "❤️ +50 HP | 🔮 +40 MP"
        }

        char = RPGCharacter(
            user_id=user_id,
            hero_class=preferred_class,
            level=1,
            xp=0,
            gold=250,
            gems=20,
            strength=hero_cfg["str"],
            agility=hero_cfg["agi"],
            intelligence=hero_cfg["int"],
            vitality=hero_cfg["str"],
            stat_points=2,
            equipment={
                "slot_1": starter_weapon,
                "slot_5": starter_armor,
                "slot_2": starter_relic
            },
            inventory=[starter_potion],
            dungeon_floor=1,
            dungeon_cleared=0,
            pvp_rating=1000,
            pvp_wins=0,
            pvp_losses=0,
            boss_kills=0
        )
        session.add(char)
        await session.commit()
        await session.refresh(char)
    else:
        from backend.db.crud.rpg.talent_tree import reset_char_talents_v2
        if reset_char_talents_v2(char):
            flag_modified(char, "talents")
            await session.commit()
            await session.refresh(char)

    return char




def serialize_character_profile(char: RPGCharacter, user_name: str = "", tg_id: Optional[int] = None) -> Dict[str, Any]:
    """Serializes character data for API response."""
    stats = calculate_character_effective_stats(char)
    h_class = str(getattr(char, "hero_class", "pudge") or "pudge").strip().lower()
    LEGACY_MAP = {
        "warrior": "juggernaut",
        "knight": "pudge",
        "paladin": "wraith_king",
        "archer": "phantom_assassin",
        "rogue": "phantom_assassin",
        "assassin": "phantom_assassin",
        "mage": "invoker",
        "wizard": "invoker"
    }
    canonical_class = LEGACY_MAP.get(h_class, h_class)
    cfg = NATAR_HEROES.get(canonical_class, NATAR_HEROES["pudge"])
    xp_needed = calculate_xp_for_level(char.level)

    talents_data = getattr(char, "talents", {}) or {}
    rebirth_essence = talents_data.get("rebirth_essence", getattr(char, "rebirth_essence", 0))
    rebirth_rank = getattr(char, "rebirths", 0)

    from backend.db.crud.rpg.rebirth import get_rebirth_rank_info, MAX_REBIRTH_RANK
    rank_info = get_rebirth_rank_info(rebirth_rank)

    from backend.db.crud.rpg.talent_tree import get_hero_available_talent_points
    avail_talent_points = get_hero_available_talent_points(char, canonical_class)

    final_tg_id = tg_id or getattr(char, "_tg_id", None)
    if final_tg_id is None:
        try:
            from sqlalchemy import inspect
            from sqlalchemy.orm.base import NO_VALUE
            insp = inspect(char)
            val = insp.attrs.user.loaded_value
            if val is not None and val is not NO_VALUE:
                final_tg_id = getattr(val, "tg_id", None)
        except Exception:
            pass

    return {
        "id": char.id,
        "user_id": char.user_id,
        "tg_id": final_tg_id,
        "user_name": user_name,
        "hero_class": canonical_class,
        "class_name": cfg["name"],
        "class_icon": cfg["icon"],
        "class_avatar": cfg.get("avatar", "🗡️"),
        "primary_attr": cfg["attr"],
        "level": char.level,
        "xp": char.xp,
        "xp_needed": xp_needed,
        "experience": char.xp,
        "experience_to_next": xp_needed,
        "gold": char.gold,
        "gems": char.gems,
        "stat_points": getattr(char, "stat_points", 0),
        "rebirths": rebirth_rank,
        "rebirth_essence": rebirth_essence,
        "rebirth_info": {
            "rank": rebirth_rank,
            "max_rank": MAX_REBIRTH_RANK,
            "title": rank_info.get("title", ""),
            "essence": rebirth_essence,
            "multiplier": stats.get("rebirth_multiplier", 1.0),
            "multiplier_pct": rank_info.get("multiplier_pct", 0),
            "next_rank": rank_info.get("next_rank"),
            "next_min_level": rank_info.get("next_min_level"),
            "next_essence_reward": rank_info.get("next_essence_reward"),
            "constellations": talents_data.get("constellations", {}),
        },
        "talent_points": avail_talent_points,
        "talents": talents_data,
        "pets": getattr(char, "pets", []),
        "strength": stats["total_strength"],
        "agility": stats["total_agility"],
        "intelligence": stats["total_intelligence"],
        "vitality": stats["total_strength"],
        "base_attributes": {
            "strength": char.strength,
            "agility": char.agility,
            "intelligence": char.intelligence,
            "vitality": char.strength
        },
        "gear_attributes": {
            "strength": stats["gear_strength"],
            "agility": stats["gear_agility"],
            "intelligence": stats["gear_intelligence"]
        },
        "total_attributes": {
            "strength": stats["total_strength"],
            "agility": stats["total_agility"],
            "intelligence": stats["total_intelligence"]
        },
        "skills": cfg.get("skills", []),
        "hero_talents": cfg.get("talents", {}),
        "progression": {
            "unlocked_features": get_unlocked_features(char.level),
            "level_cap": LEVEL_CAP,
            "stat_points_per_level": STAT_POINTS_PER_LEVEL
        },
        "stats": stats,
        "equipment": char.equipment,
        "inventory": char.inventory,
        "dungeon_floor": char.dungeon_floor,
        "dungeon_cleared": char.dungeon_cleared,
        "pvp_rating": char.pvp_rating,
        "pvp_wins": char.pvp_wins,
        "pvp_losses": char.pvp_losses,
        "boss_kills": char.boss_kills
    }


