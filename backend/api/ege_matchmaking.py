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

    room.webapp_url = base_url
    if not hasattr(room, "matchmaking_messages"):
        room.matchmaking_messages = []

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
            sent_msg = await asyncio.wait_for(
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
            # If an opponent joined while send_message was in flight
            if room.status != "waiting" or room.opponent_tg_id is not None:
                participants = {int(room.host_tg_id)}
                if room.opponent_tg_id:
                    participants.add(int(room.opponent_tg_id))
                msg_id = getattr(sent_msg, "message_id", None) or getattr(sent_msg, "id", None)
                if recipient_id not in participants:
                    if msg_id and hasattr(bot, "delete_message"):
                        try:
                            await bot.delete_message(chat_id=recipient_id, message_id=msg_id)
                        except Exception:
                            pass
                else:
                    room.matchmaking_messages.append((recipient_id, msg_id))
                break

            msg_id = getattr(sent_msg, "message_id", None) or getattr(sent_msg, "id", None) or 1
            room.matchmaking_messages.append((recipient_id, msg_id))
            sent_count += 1
            room.matchmaking_recipient_count = sent_count
        except Exception:
            logger.warning("Could not send EGE matchmaking invite to %s", recipient_id, exc_info=True)
        await asyncio.sleep(0.05)

    if room.status != "waiting" or room.opponent_tg_id is not None:
        await delete_matchmaking_messages(bot, room, keep_participants=True)


async def delete_matchmaking_messages(bot, room, keep_participants: bool = False) -> int:
    """Delete matchmaking invite messages sent in Telegram for this room.

    If keep_participants is True, messages sent to players who participated in the duel
    are preserved so they can be edited with final results upon completion.
    """
    if not bot or not getattr(room, "matchmaking_messages", None):
        return 0

    participants: set[int] = set()
    if keep_participants:
        if getattr(room, "host_tg_id", None):
            participants.add(int(room.host_tg_id))
        if getattr(room, "opponent_tg_id", None):
            participants.add(int(room.opponent_tg_id))

    to_delete: list[tuple[int, int]] = []
    to_keep: list[tuple[int, int]] = []

    for chat_id, message_id in room.matchmaking_messages:
        if keep_participants and int(chat_id) in participants:
            to_keep.append((chat_id, message_id))
        else:
            to_delete.append((chat_id, message_id))

    room.matchmaking_messages = to_keep

    deleted = 0
    for chat_id, message_id in to_delete:
        if hasattr(bot, "delete_message"):
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                deleted += 1
            except Exception:
                logger.debug("Failed to delete matchmaking message %s in chat %s", message_id, chat_id)
    if deleted:
        logger.info("Deleted %s matchmaking messages for room %s", deleted, getattr(room, "room_id", ""))
    return deleted


def on_opponent_joined_matchmaking(room, keep_participants: bool = True) -> None:
    """Trigger deletion of non-participant matchmaking messages when opponent joins or room cancelled."""
    if not getattr(room, "matchmaking_search", False):
        return
    try:
        from backend.bot.bot import get_current_bot
        bot = get_current_bot()
        if bot:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(delete_matchmaking_messages(bot, room, keep_participants=keep_participants))
            except RuntimeError:
                asyncio.run(delete_matchmaking_messages(bot, room, keep_participants=keep_participants))
    except Exception:
        logger.debug("Could not schedule matchmaking message deletion", exc_info=True)


def format_duel_result_text(room: Any, viewer_chat_id: int) -> str:
    """Format duel results for Telegram message, personalized for the recipient."""
    host_id = int(getattr(room, "host_tg_id", 0) or 0)
    opp_id = int(getattr(room, "opponent_tg_id", 0) or 0)
    host_name = html.escape(str(getattr(room, "host_name", "Хост") or "Хост"))
    opp_name = html.escape(str(getattr(room, "opponent_name", "Соперник") or "Соперник"))
    game_type = getattr(room, "game_type", "ege_stress_duel")
    game_label = _DUEL_NAMES.get(game_type, "ЕГЭ-дуэль")

    host_errors = room._errors(host_id) if hasattr(room, "_errors") else 0
    opp_errors = room._errors(opp_id) if hasattr(room, "_errors") else 0
    host_answers = len(room.answers.get(host_id, [])) if hasattr(room, "answers") else 0
    opp_answers = len(room.answers.get(opp_id, [])) if hasattr(room, "answers") else 0
    host_score = max(0, host_answers - host_errors)
    opp_score = max(0, opp_answers - opp_errors)
    round_size = getattr(room, "round_size", 10)
    winner = getattr(room, "winner", None)
    winner_int = int(winner) if winner is not None else None

    if winner_int is None:
        status_line = "🤝 <b>Ничья!</b>"
    elif viewer_chat_id == winner_int:
        status_line = "🏆 <b>Вы победили!</b>"
    elif viewer_chat_id in (host_id, opp_id):
        status_line = "😔 <b>Вы проиграли</b>"
    else:
        winner_name = host_name if winner_int == host_id else opp_name
        status_line = f"🏆 Победитель: <b>{winner_name}</b>"

    rating_line = ""
    changes = getattr(room, "rating_changes", {}) or {}
    if viewer_chat_id in changes:
        delta = changes[viewer_chat_id]
        sign = "+" if delta > 0 else ""
        rating_line = f"\n📈 Рейтинг: <b>{sign}{delta} MMR</b>" if delta >= 0 else f"\n📉 Рейтинг: <b>{delta} MMR</b>"

    text = (
        f"⚔️ <b>Результаты ЕГЭ-дуэли</b> ({game_label})\n\n"
        f"{status_line}\n\n"
        f"👤 <b>{host_name}</b>: {host_score} из {round_size}\n"
        f"👤 <b>{opp_name}</b>: {opp_score} из {round_size}\n\n"
        f"📊 Итоговый счёт: <b>{host_score} : {opp_score}</b>"
        f"{rating_line}"
    )
    return text


async def edit_duel_result_messages(bot, room: Any) -> int:
    """Edit duel messages in Telegram to display the final scores and results."""
    if not bot:
        return 0

    messages_to_edit: list[tuple[int, int]] = []
    if getattr(room, "matchmaking_messages", None):
        messages_to_edit.extend(room.matchmaking_messages)
    direct_msg_id = getattr(room, "invite_msg_id", None)
    direct_chat_id = getattr(room, "invite_chat_id", None)
    if direct_msg_id and direct_chat_id:
        if (direct_chat_id, direct_msg_id) not in messages_to_edit:
            messages_to_edit.append((direct_chat_id, direct_msg_id))

    if not messages_to_edit:
        return 0

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    base_url = getattr(room, "webapp_url", "") or ""
    keyboard = None
    if base_url:
        button = InlineKeyboardButton(
            text="🎓 Арена ЕГЭ",
            web_app=WebAppInfo(url=base_url) if base_url.startswith("https://") else None,
            url=None if base_url.startswith("https://") else base_url,
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    edited_count = 0
    for chat_id, message_id in messages_to_edit:
        text = format_duel_result_text(room, chat_id)
        if hasattr(bot, "edit_message_text"):
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                edited_count += 1
            except Exception as e:
                logger.debug("Failed to edit duel result message %s in chat %s: %s", message_id, chat_id, e)

    if edited_count:
        logger.info("Edited %s duel result messages for room %s", edited_count, getattr(room, "room_id", ""))
    return edited_count


def on_ege_duel_finished(room: Any) -> None:
    """Schedule editing of duel messages when a duel is finalized."""
    if getattr(room, "results_notified", False):
        return
    room.results_notified = True
    try:
        from backend.bot.bot import get_current_bot
        bot = get_current_bot()
        if bot:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(edit_duel_result_messages(bot, room))
            except RuntimeError:
                asyncio.run(edit_duel_result_messages(bot, room))
    except Exception:
        logger.debug("Could not schedule duel result message edit", exc_info=True)
