import logging
import zoneinfo
from datetime import datetime
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramAPIError

from backend.config import settings
from backend.db.session import async_session_factory
from backend.db.crud.custom_schedule import get_due_custom_schedules, mark_schedule_sent

logger = logging.getLogger(__name__)

DAYS_RU_ACC = {
    1: "понедельник",
    2: "вторник",
    3: "среду",
    4: "четверг",
    5: "пятницу",
    6: "субботу",
    7: "воскресенье",
}


async def send_due_custom_schedules(bot: Bot) -> int:
    """
    Проверяет базу данных и рассылает пользователям их персональные расписания,
    запланированные на текущую минуту.
    Устойчиво к перезапускам и защищено от дубликатов с помощью last_sent_date.
    """
    try:
        tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    current_date = now.date()
    current_time = f"{now.hour:02d}:{now.minute:02d}"
    day_of_week = current_date.isoweekday()  # 1 = Monday .. 7 = Sunday
    day_name = DAYS_RU_ACC.get(day_of_week, "сегодня")

    sent_count = 0

    try:
        async with async_session_factory() as session:
            due_list = await get_due_custom_schedules(
                session,
                day_of_week=day_of_week,
                current_time=current_time,
                current_date=current_date,
            )

            if not due_list:
                return 0

            logger.info(
                f"Found {len(due_list)} due custom schedule(s) for {current_time} ({day_name})."
            )

            for sched in due_list:
                delivered = False
                try:
                    if sched.content_type == "photo" and sched.file_id:
                        caption = f"📅 <b>Ваше расписание на {day_name}</b>"
                        await bot.send_photo(
                            chat_id=sched.user_tg_id,
                            photo=sched.file_id,
                            caption=caption,
                            parse_mode="HTML",
                        )
                        delivered = True
                    elif sched.content_type == "text" and sched.text_content:
                        text = (
                            f"📅 <b>Ваше расписание на {day_name}:</b>\n\n"
                            f"{sched.text_content}"
                        )
                        await bot.send_message(
                            chat_id=sched.user_tg_id,
                            text=text,
                            parse_mode="HTML",
                        )
                        delivered = True
                except TelegramForbiddenError:
                    logger.warning(
                        f"Custom schedule: bot was blocked by user {sched.user_tg_id}. Skipping."
                    )
                    # Помечаем отправленным, чтобы не долбиться каждую минуту
                    delivered = True
                except TelegramBadRequest as ex:
                    logger.error(
                        f"Telegram BadRequest sending custom schedule to {sched.user_tg_id}: {ex}"
                    )
                    delivered = True
                except TelegramAPIError as ex:
                    logger.error(
                        f"Telegram API error sending custom schedule to {sched.user_tg_id}: {ex}"
                    )
                except Exception as ex:
                    logger.error(
                        f"Unexpected error sending custom schedule to {sched.user_tg_id}: {ex}"
                    )

                if delivered:
                    try:
                        await mark_schedule_sent(session, sched.id, current_date)
                        sent_count += 1
                    except Exception as ex:
                        logger.error(f"Failed to mark custom schedule {sched.id} as sent: {ex}")

    except Exception as ex:
        logger.error(f"Error in send_due_custom_schedules job: {ex}")

    if sent_count > 0:
        logger.info(f"Successfully dispatched {sent_count} custom schedule(s).")
    return sent_count
