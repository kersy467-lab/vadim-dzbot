import html
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.services.facts import get_or_generate_daily_fact, format_fact_telegram_message

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("fact"))
@router.message(Command("interesting_fact"))
@router.message(Command("fact_day"))
@router.message(F.text == "💡 Интересный факт")
async def show_daily_fact(message: Message, db_session: AsyncSession):
    try:
        fact = await get_or_generate_daily_fact(db_session)
        text = format_fact_telegram_message(fact)
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error presenting interesting fact: {e}")
        try:
            from backend.bot.services.facts import get_curated_fact_for_slot
            from backend.config import get_current_date_hour_minute
            today, hour, minute = get_current_date_hour_minute()
            c = get_curated_fact_for_slot(today, hour, minute)
            text = (
                "💡 <b>Интересный факт</b>\n"
                f"🏷 <b>{html.escape(c['category'])}</b> | <i>{html.escape(c['title'])}</i>\n\n"
                f"{html.escape(c['fact'])}\n\n"
                "✨ <i>Каждый день — новое открытие!</i>"
            )
            await message.answer(text, parse_mode="HTML")
        except Exception as inner_e:
            logger.error(f"Emergency fallback failed: {inner_e}")
            await message.answer("💡 Интересный факт пока загружается. Попробуйте еще раз через мгновение!")


