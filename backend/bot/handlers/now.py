import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

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
@router.message(F.text.in_({"⏳ Сейчас", "⏳ Какой сейчас урок?", "Какой сейчас урок?", "какой сейчас урок", "какой урок", "сейчас", "урок"}))
async def cmd_now(message: Message, db_session: AsyncSession):
    """Обработчик команды /now и кнопки '⏳ Сейчас'."""
    text = await get_now_lesson_status(db_session)
    await message.answer(
        text=text,
        reply_markup=get_now_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "now_refresh")
async def cb_now_refresh(callback: CallbackQuery, db_session: AsyncSession):
    """Обновляет статус звонков и уроков в реальном времени."""
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
