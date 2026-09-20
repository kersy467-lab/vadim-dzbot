import asyncio
import logging
from datetime import datetime, date
import zoneinfo
from aiogram import Bot

from backend.config import settings, get_today
from backend.db.session import async_session_factory
from backend.db.crud.users import get_canteen_reminder_users
from backend.db.crud.bells import get_bell_schedule_for_date
from backend.db.crud.duty import get_class_setting, set_class_setting

logger = logging.getLogger(__name__)

CANTEEN_MESSAGES = [
    "🔔 <b>Звонок с 5-го урока!</b>",
    "🏃‍♂️ <b>Бегом в столовую</b>, пока там есть горячая еда и свежая выпечка!",
    "🥐 <b>Приятного аппетита, 11 «Б»!</b> 😋"
]


async def send_canteen_reminder(bot: Bot, force: bool = False) -> int:
    """
    Отправляет 3 последовательных сообщения в ЛС всем ученикам с включённой настройкой.
    Возвращает количество уведомлённых пользователей.
    """
    today = get_today()
    async with async_session_factory() as session:
        if not force:
            last_date = await get_class_setting(session, "last_canteen_reminder_date")
            if last_date == str(today):
                logger.info("Canteen reminder already sent today, skipping.")
                return 0

        users = await get_canteen_reminder_users(session)
        if not users:
            logger.info("No users with canteen reminder enabled.")
            if not force:
                await set_class_setting(session, "last_canteen_reminder_date", str(today))
            return 0

        if not force:
            await set_class_setting(session, "last_canteen_reminder_date", str(today))

    count = 0
    for user in users:
        if not user.tg_id or user.tg_id <= 0:
            continue
        try:
            for i, text in enumerate(CANTEEN_MESSAGES):
                await bot.send_message(
                    chat_id=user.tg_id,
                    text=text,
                    parse_mode="HTML"
                )
                if i < len(CANTEEN_MESSAGES) - 1:
                    await asyncio.sleep(1.2)
            count += 1
        except Exception as e:
            logger.warning(f"Could not send canteen reminder to {user.tg_id}: {e}")

    logger.info(f"Canteen reminder sent to {count} students.")
    return count


async def check_canteen_time_job(bot: Bot):
    """
    Запускается планировщиком каждую минуту по будням (пн-пт).
    Проверяет, наступило ли время окончания 5-го урока.
    """
    tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
    now = datetime.now(tz)

    # Работает только в учебные дни: Пн(0) - Пт(4)
    if now.weekday() > 4:
        return

    today = now.date()
    current_time_str = now.strftime("%H:%M")

    target_time = "12:45"
    try:
        async with async_session_factory() as session:
            bells = await get_bell_schedule_for_date(session, today)
            for b in bells:
                if b.lesson_number == 5 and b.end_time:
                    target_time = b.end_time.strip()
                    break
    except Exception as e:
        logger.warning(f"Could not fetch dynamic bell for canteen check: {e}")

    if current_time_str == target_time:
        logger.info(f"5th lesson ended ({target_time})! Triggering canteen reminder...")
        await send_canteen_reminder(bot, force=False)
