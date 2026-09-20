import logging
from datetime import date
from collections import defaultdict
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_today
from backend.db.session import async_session_factory
from backend.db.crud.birthdays import (
    get_all_birthdays,
    get_birthdays_for_date,
    get_upcoming_birthdays,
    seed_default_birthdays,
    MONTH_NAMES_NOMINATIVE,
    MONTH_NAMES_GENITIVE
)

logger = logging.getLogger(__name__)

router = Router()

SEASON_EMOJIS = {
    12: "❄️ Зима", 1: "❄️ Зима", 2: "❄️ Зима",
    3: "🌸 Весна", 4: "🌸 Весна", 5: "🌸 Весна",
    6: "☀️ Лето", 7: "☀️ Лето", 8: "☀️ Лето",
    9: "🍂 Осень", 10: "🍂 Осень", 11: "🍂 Осень"
}


async def build_birthdays_overview_text(session: AsyncSession, today: date) -> str:
    """Формирует структурированный текст календаря дней рождения 11 «Б» класса."""
    # Убедимся, что данные засеяны
    await seed_default_birthdays(session)

    all_b = await get_all_birthdays(session)
    todays = await get_birthdays_for_date(session, today.day, today.month)
    upcoming = await get_upcoming_birthdays(session, today, limit=3)

    lines = [
        "🎂 **Дни рождения нашего класса** 🎈",
        "──────────────────────"
    ]

    # 1. Если сегодня у кого-то ДР
    if todays:
        names = ", ".join(f"**{s.full_name}**" for s in todays)
        lines.append(f"🎉 **СЕГОДНЯ ДЕНЬ РОЖДЕНИЯ:**")
        lines.append(f"✨ {names} — поздравляем от всего класса! 🥳🍰\n")

    # 2. Ближайшие именинники
    if upcoming:
        lines.append("⏳ **Ближайшие именинники:**")
        for idx, u in enumerate(upcoming, 1):
            if u["days_left"] == 0:
                left_str = "🎉 **СЕГОДНЯ!**"
            elif u["days_left"] == 1:
                left_str = "*(завтра!)*"
            elif 2 <= u["days_left"] <= 4:
                left_str = f"*(через {u['days_left']} дня)*"
            else:
                left_str = f"*(через {u['days_left']} дней)*"

            lines.append(f"  {idx}. **{u['name']}** — {u['date_str']} {left_str}")
        lines.append("──────────────────────")

    # 3. Полный список по месяцам
    lines.append("📅 **Календарный список класса:**\n")

    # Группируем по месяцам (1..12)
    by_month = defaultdict(list)
    for b in all_b:
        by_month[b.birth_month].append(b)

    for m in range(1, 13):
        students = by_month.get(m, [])
        if not students:
            continue

        month_title = MONTH_NAMES_NOMINATIVE.get(m, "")
        season = SEASON_EMOJIS.get(m, "")
        lines.append(f"**{month_title}** ({season}):")

        for s in students:
            is_today = (s.birth_day == today.day and s.birth_month == today.month)
            star = " 🌟 *(СЕГОДНЯ)*" if is_today else ""
            lines.append(f"  • {s.full_name} — `{s.birth_day:02d}.{s.birth_month:02d}`{star}")
        lines.append("")

    lines.append("✨ *Поздравления приходят автоматически в 00:00 в беседу класса!*")
    return "\n".join(lines)


@router.message(F.text == "🎂 Дни рождения")
@router.message(Command("birthdays"))
async def cmd_birthdays(message: Message):
    """Показывает календарь дней рождения учеников класса."""
    today = get_today()
    async with async_session_factory() as session:
        text = await build_birthdays_overview_text(session, today)
        await message.answer(
            text,
            parse_mode="Markdown"
        )


@router.callback_query(F.data == "birthdays_refresh")
async def cb_birthdays_refresh(callback: CallbackQuery):
    """Обработка нажатия на устаревшую кнопку обновления."""
    today = get_today()
    async with async_session_factory() as session:
        text = await build_birthdays_overview_text(session, today)
        try:
            await callback.message.edit_text(text, parse_mode="Markdown")
            await callback.answer("Список актуален!")
        except Exception:
            await callback.answer("Данные актуальны.")
