"""Telegram-facing EGE Arena profile, nickname and /stats commands."""
from __future__ import annotations

import html
import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import get_user_by_ege_nickname, set_ege_nickname
from backend.db.models import User
from backend.ege.ranking import get_player_profile
from backend.bot.keyboards.main_menu import get_arena_keyboard, get_main_keyboard
from backend.db.crud import has_full_access

router = Router(name="ege_arena_router")


class NicknameSetupStates(StatesGroup):
    entering_nickname = State()


async def ask_for_nickname(message: Message, state: FSMContext, *, first_time: bool = False) -> None:
    await state.set_state(NicknameSetupStates.entering_nickname)
    intro = "Добро пожаловать в <b>ЕГЭ Арену</b>!\n\n" if first_time else ""
    await message.answer(
        intro + "Введите игровой ник (2–24 символа). Он будет виден в дуэлях и рейтинге.\n"
        "Разрешены буквы, цифры, <code>_</code>, <code>-</code> и точка.",
        parse_mode="HTML",
    )


@router.message(NicknameSetupStates.entering_nickname)
async def save_nickname(message: Message, state: FSMContext, db_session: AsyncSession, current_user: User | None):
    if not current_user:
        await message.answer("Сначала отправьте /start")
        await state.clear()
        return
    ok, result = await set_ege_nickname(db_session, current_user, message.text or "")
    if not ok:
        await message.answer(f"⚠️ {html.escape(result)}", parse_mode="HTML")
        return
    await state.clear()
    full = has_full_access(current_user)
    keyboard = get_main_keyboard(
        is_admin=current_user.role == "admin",
        user_id=current_user.tg_id,
        is_tester=bool(getattr(current_user, "is_tester", False)),
        flag_b=bool(getattr(current_user, "flag_b", False)),
    ) if full else get_arena_keyboard(current_user.tg_id)
    await message.answer(
        f"✅ Ник установлен: <b>{html.escape(result)}</b>\n\n"
        "Теперь можно играть рейтинговые дуэли по ударениям и словарным словам.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.message(Command("nick"))
@router.message(F.text == "✏️ Сменить ник")
async def change_nickname(message: Message, state: FSMContext, current_user: User | None):
    if not current_user:
        await message.answer("Сначала отправьте /start")
        return
    await ask_for_nickname(message, state)


def _stats_caption(profile: dict) -> str:
    place = f"#{profile['top_position']}" if profile.get("top_position") else "—"
    return (
        f"👤 <b>{html.escape(str(profile.get('nickname') or 'Игрок'))}</b>\n\n"
        f"🏆 <b>{int(profile.get('rating') or 0)} MMR</b>\n"
        f"🏅 Ранг: <b>{html.escape(str(profile.get('rank') or 'Рекрут'))}</b>\n\n"
        f"⚔ Победы: <b>{int(profile.get('wins') or 0)}</b>\n"
        f"💀 Поражения: <b>{int(profile.get('losses') or 0)}</b>\n"
        f"🤝 Ничьи: <b>{int(profile.get('draws') or 0)}</b>\n"
        f"🎮 Матчей: <b>{int(profile.get('matches') or 0)}</b>\n\n"
        f"📈 Место в общем топе: <b>{place}</b>\n"
        "<i>Топ обновляется раз в 10 минут.</i>"
    )


async def _send_stats(message: Message, profile: dict) -> None:
    caption = _stats_caption(profile)
    image_path = str(profile.get("rank_image_path") or "")
    if image_path and os.path.exists(image_path):
        await message.answer_photo(FSInputFile(image_path), caption=caption, parse_mode="HTML")
    else:
        await message.answer(caption, parse_mode="HTML")


@router.message(Command("stats"))
async def stats_command(message: Message, db_session: AsyncSession, current_user: User | None):
    if not current_user:
        await message.answer("Сначала отправьте /start")
        return
    parts = (message.text or "").split(maxsplit=1)
    target = current_user
    if len(parts) == 2 and parts[1].strip():
        target = await get_user_by_ege_nickname(db_session, parts[1].strip())
        if not target:
            await message.answer(f'Игрок с ником "{html.escape(parts[1].strip())}" не найден.', parse_mode="HTML")
            return
    await _send_stats(message, await get_player_profile(db_session, target))


@router.message(F.text == "📊 Моя статистика")
async def my_stats_button(message: Message, db_session: AsyncSession, current_user: User | None):
    if not current_user:
        await message.answer("Сначала отправьте /start")
        return
    await _send_stats(message, await get_player_profile(db_session, current_user))
