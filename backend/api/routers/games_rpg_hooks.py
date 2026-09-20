import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User

logger = logging.getLogger(__name__)

def get_public_webapp_url(request: Request) -> str:
    """Returns reliable public HTTPS URL of the Mini App, auto-detecting proxy/tunnel domains."""
    from backend.config import settings
    configured = settings.WEBAPP_URL.strip() if settings.WEBAPP_URL else ""
    if configured and not ("localhost" in configured or "127.0.0.1" in configured):
        return configured

    ref = request.headers.get("referer")
    if ref and ref.startswith("https://"):
        return ref.split("?")[0].split("#")[0]

    origin = request.headers.get("origin")
    if origin and origin.startswith("https://"):
        return f"{origin.rstrip('/')}/app"

    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "https")
    if host and not ("localhost" in host or "127.0.0.1" in host):
        return f"{proto}://{host}/app"

    return configured or "https://t.me"

async def send_game_invite_notification(
    bot,
    opponent_tg_id: int,
    invite_text: str,
    reply_markup
):
    """Sends invitation to opponent in the background without blocking the HTTP request."""
    try:
        await asyncio.wait_for(
            bot.send_message(
                chat_id=opponent_tg_id,
                text=invite_text,
                reply_markup=reply_markup
            ),
            timeout=8.0
        )
        logger.info(f"Game invitation notification sent to {opponent_tg_id}")
    except Exception as e:
        logger.warning(f"Could not deliver game invitation to {opponent_tg_id}: {e}")


async def prepare_rpg_hero_data(session: AsyncSession, user: Optional[User], host_name: str) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    try:
        from backend.db.crud.rpg import get_or_create_rpg_character, serialize_character_profile
        char = await get_or_create_rpg_character(session, user_id=user.id)
        return serialize_character_profile(char, user_name=host_name)
    except Exception as e:
        logger.warning(f"Could not load hero_data for game room: {e}")
        return None

def get_rpg_invite_details(room: Any, game_type: str, base_url: str, separator: str, opponent_tg_id: int, escaped_host_name: str) -> Tuple[str, str, str]:
    if game_type == "rpg_duel":
        game_url = f"{base_url}{separator}room={room.room_id}&game=rpg_duel&tg_user_id={opponent_tg_id}"
        invite_text = (
            f"⚔️ <b>{escaped_host_name}</b> бросает тебе вызов на <b>Dota 2 PvP Дуэль 1v1</b>!\n\n"
            f"⚡ Проверь своего персонажа в честном бою на арене!"
        )
        btn_text = "⚔️ Принять вызов на Дуэль"
        return game_url, invite_text, btn_text
    elif game_type == "rpg_coop":
        game_url = f"{base_url}{separator}room={room.room_id}&game=rpg_coop&tg_user_id={opponent_tg_id}"
        boss_name = getattr(room, "boss", {}).get("name", "Босс")
        boss_icon = getattr(room, "boss", {}).get("icon", "🐲")
        invite_text = (
            f"{boss_icon} <b>{escaped_host_name}</b> зовет тебя в совместный <b>Рейд на {boss_name}</b>!\n\n"
            f"🛡️ Готов объединить силы и выбить легендарный дроп?"
        )
        btn_text = "🛡️ Вступить в Рейд"
        return game_url, invite_text, btn_text
    return "", "", ""

async def handle_rpg_room_joined(room: Any, session: AsyncSession, user: Optional[User], user_name: str):
    if not room or not hasattr(room, "sync_character_data"):
        return

    g_type = getattr(room, "game_type", None)
    if g_type in ["rpg_duel", "rpg_coop"]:
        try:
            from backend.db.crud.rpg import get_or_create_rpg_character, serialize_character_profile
            char = await get_or_create_rpg_character(session, user_id=user.id if user else 1)
            prof = serialize_character_profile(char, user_name=user_name)

            if g_type == "rpg_duel":
                room.sync_character_data("opponent", prof)
            elif g_type == "rpg_coop":
                role = room.get_player_role(user.tg_id if user else 0)
                if role:
                    room.sync_character_data(role, prof)
        except Exception as e:
            logger.warning(f"Could not sync stats for {g_type}: {e}")

async def handle_rpg_room_moved(room: Any, session: AsyncSession, user: Optional[User], viewer_tg_id: Optional[int] = None):
    if room and getattr(room, "game_type", None) == "rpg_coop" and room.status == "finished" and room.winner == "heroes":
        if not getattr(room, "reward_distributed", False):
            room.reward_distributed = True
            try:
                from sqlalchemy import select
                from backend.db.crud.rpg import get_or_create_rpg_character, add_xp_and_gold_to_character, open_boss_raid_chest
                boss_gold = room.boss.get("gold_reward", 1000)
                boss_xp = room.boss.get("xp_reward", 750)

                # Gather all real human participants from the coop room
                participants_tg_ids = set()
                players_dict = getattr(room, "players", {}) or {}
                for role_key in ["host", "player_2", "player_3"]:
                    p_info = players_dict.get(role_key)
                    if p_info and not p_info.get("is_bot") and p_info.get("tg_id") and p_info.get("name") != "Свободный слот":
                        participants_tg_ids.add(p_info["tg_id"])
                if viewer_tg_id and viewer_tg_id > 0:
                    participants_tg_ids.add(viewer_tg_id)
                if user and getattr(user, "tg_id", None):
                    participants_tg_ids.add(user.tg_id)

                rewarded_user_ids = set()
                primary_char = None

                for tid in participants_tg_ids:
                    q = select(User).where(User.tg_id == tid)
                    u_obj = (await session.execute(q)).scalar_one_or_none()
                    if u_obj and u_obj.id not in rewarded_user_ids:
                        rewarded_user_ids.add(u_obj.id)
                        c = await get_or_create_rpg_character(session, user_id=u_obj.id)
                        await add_xp_and_gold_to_character(session, c, xp_amount=boss_xp, gold_amount=boss_gold)
                        c.boss_kills = getattr(c, "boss_kills", 0) + 1
                        if primary_char is None:
                            primary_char = c

                # Fallback if no matching User was registered via tg_id (e.g. guest/demo session)
                if not rewarded_user_ids:
                    uid = user.id if user else 1
                    c = await get_or_create_rpg_character(session, user_id=uid)
                    await add_xp_and_gold_to_character(session, c, xp_amount=boss_xp, gold_amount=boss_gold)
                    c.boss_kills = getattr(c, "boss_kills", 0) + 1
                    primary_char = c

                chest_res = await open_boss_raid_chest(session, primary_char, boss_id=room.boss.get("id", "roshan"))
                room.victory_rewards = {
                    "boss_name": room.boss.get("name"),
                    "boss_icon": room.boss.get("icon"),
                    "gold_earned": boss_gold + chest_res.get("gold_reward", 0),
                    "xp_earned": boss_xp,
                    "gems_earned": chest_res.get("gems_reward", 25),
                    "chest": chest_res,
                    "item": chest_res.get("item")
                }
                await session.commit()
            except Exception as ex:
                logger.warning(f"Could not award coop boss reward: {ex}")
