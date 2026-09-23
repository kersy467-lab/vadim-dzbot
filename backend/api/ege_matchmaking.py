"""Helpers for starting EGE duel searches and notifying ranked players."""
from __future__ import annotations

import asyncio
import html
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.ege import ranking

logger = logging.getLogger(__name__)

_DUEL_NAMES = {
    "ege_stress_duel": "ударения",
    "ege_vocabulary_duel": "словарные слова",
}


async def get_matchmaking_candidate_ids(session: AsyncSession, host_tg_id: int) -> list[int]:
    """Return ranked EGE players who have not disabled bot notifications."""
    rows = await ranking.get_leaderboard(session)
    ranked_ids = [
        int(row["tg_id"])
        for row in rows
        if int(row.get("tg_id") or 0) > 0 and int(row["tg_id"]) != int(host_tg_id)
    ]
    if not ranked_ids:
        return []

    result = await session.execute(
        select(User.tg_id).where(
            User.tg_id.in_(ranked_ids),
            User.notifications_enabled.is_(True),
        )
    )
    enabled_ids = {int(tg_id) for tg_id in result.scalars().all()}
    # Preserve the MMR order from the existing top-100 roster.
    return [tg_id for tg_id in ranked_ids if tg_id in enabled_ids]


async def send_matchmaking_notifications(bot, room, recipient_ids: list[int], base_url: str) -> None:
    """Send a join button to each ranked player until the room is claimed or canceled."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    game_label = _DUEL_NAMES.get(room.game_type, "ЕГЭ-дуэли")
    host_name = html.escape(str(room.host_name or "Игрок"))
    separator = "&" if "?" in base_url else "?"
    sent_count = 0

    for recipient_id in recipient_ids:
        if room.status != "waiting" or room.opponent_tg_id is not None:
            break
        game_url = (
            f"{base_url}{separator}room={room.room_id}"
            f"&game={room.game_type}&tg_user_id={recipient_id}"
        )
        button = InlineKeyboardButton(
            text="⚔️ Принять дуэль",
            web_app=WebAppInfo(url=game_url) if game_url.startswith("https://") else None,
            url=None if game_url.startswith("https://") else game_url,
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
        try:
            await asyncio.wait_for(
                bot.send_message(
                    chat_id=recipient_id,
                    text=(
                        f"🎓 <b>{host_name}</b> ищет соперника для ЕГЭ-дуэли!\n"
                        f"Режим: <b>{game_label}</b>\n\n"
                        "Нажми кнопку, чтобы присоединиться. В дуэль попадёт первый игрок, который откроет приглашение."
                    ),
                    reply_markup=keyboard,
                    parse_mode="HTML",
                ),
                timeout=8.0,
            )
            sent_count += 1
            room.matchmaking_recipient_count = sent_count
        except Exception:
            logger.warning("Could not send EGE matchmaking invite to %s", recipient_id, exc_info=True)
        await asyncio.sleep(0.05)
