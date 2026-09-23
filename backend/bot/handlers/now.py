import logging
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import User
from backend.bot.services.now import get_now_lesson_status

logger = logging.getLogger(__name__)

router = Router(name="now_router")


def get_now_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="now_refresh"),
                InlineKeyboardButton(text="📅 Расписание", callback_data="sched_today")
            ]
        ]
    )


@router.message(Command("now"))
@router.message(F.text == "⏳ Сейчас")
async def cmd_now(message: Message, db_session: AsyncSession, current_user: Optional[User] = None):
    """Обработчик команды /now и кнопки '⏳ Сейчас'."""
    if current_user is not None:
        is_adm = (current_user.role == "admin") or (
            bool(settings.ADMIN_ID) and bool(message.from_user) and message.from_user.id == settings.ADMIN_ID
        )
        if not is_adm and not getattr(current_user, "flag_b", False):
            await message.answer(
                "🔒 Доступ к текущему уроку и расписанию 11 «Б» закрыт. Обратитесь к администратору для включения доступа."
            )
            return

    text = await get_now_lesson_status(db_session)
    await message.answer(
        text=text,
        reply_markup=get_now_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "now_refresh")
async def cb_now_refresh(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    """Обновляет статус звонков и уроков в реальном времени."""
    if current_user is not None:
        is_adm = (current_user.role == "admin") or (
            bool(settings.ADMIN_ID) and bool(callback.from_user) and callback.from_user.id == settings.ADMIN_ID
        )
        if not is_adm and not getattr(current_user, "flag_b", False):
            await callback.answer("🔒 Доступ к расписанию закрыт.", show_alert=True)
            return

    text = await get_now_lesson_status(db_session)
    if callback.message and callback.message.text == text:
        await callback.answer("Данные уже актуальны ⏳")
        return

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_now_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer("Обновлено! 🔄")
    except Exception as e:
        logger.debug(f"Failed to edit message in cb_now_refresh: {e}")
        await callback.answer("Обновлено! 🔄")
