import logging
import asyncio
from datetime import date
from typing import List, Optional
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_today
from backend.db.session import async_session_factory
from backend.db.models import StudentBirthday
from backend.db.crud import (
    get_birthdays_for_date,
    get_approved_group_chats,
    get_class_setting,
    set_class_setting
)
from backend.db.crud.birthdays import MONTH_NAMES_GENITIVE

logger = logging.getLogger(__name__)


def format_birthday_message(students: List[StudentBirthday], target_date: Optional[date] = None) -> str:
    """Формирует красивое и теплое поздравление от имени 11 «Б» класса."""
    if not students:
        return ""

    if target_date is None:
        target_date = get_today()

    day = target_date.day
    month_name = MONTH_NAMES_GENITIVE.get(target_date.month, "сегодня")

    if len(students) == 1:
        if students[0].full_name.strip().lower() == "исайкин":
            return "Исайкин с днем рождения!!!! 🎂🍰🎆🎇"
        name = students[0].full_name
        return (
            f"🎉🎂 **С ДНЁМ РОЖДЕНИЯ, {name}!** 🎂🎉\n\n"
            "Сегодня наш класс поздравляет тебя с твоим праздником! 🥳✨\n\n"
            "От всей души желаем:\n"
            "🌟 **100 баллов на ЕГЭ** и лёгкого поступления в вуз мечты!\n"
            "🚀 **Достижения всех поставленных целей** и море вдохновения!\n"
            "💪 **Крепкого здоровья**, неиссякаемой энергии и сил на весь 11 класс!\n"
            "☀️ **Верных друзей рядом** и самых ярких школьных воспоминаний!\n\n"
            "Пусть этот год станет стартом для твоих самых крутых побед! Ура! 🎁🥳🎈"
        )

    names_str = "\n".join(f"👑 **{s.full_name}**" for s in students)
    return (
        "🎉🎂 **С ДНЁМ РОЖДЕНИЯ!** 🎂🎉\n\n"
        "Сегодня особенный праздничный день — сразу несколько именинников в нашем классе! 🥳✨\n\n"
        "Поздравляем:\n"
        f"{names_str}\n\n"
        "От всего нашего класса желаем вам:\n"
        "🌟 **100 баллов на ЕГЭ** и блестящего поступления!\n"
        "🚀 **Уверенности в своих силах** и покорения любых высот!\n"
        "💪 **Крепкого здоровья**, отличного настроения и незабываемого выпускного года!\n"
        "☀️ **Верных друзей рядом**, удачи и море позитива каждый день!\n\n"
        "Пусть этот праздничный день принесет множество крутых эмоций и исполнение желаний! Ура! 🎁🥳🎈"
    )


async def check_and_send_birthday_greetings(bot: Bot, force: bool = False) -> int:
    """
    Проверяет, есть ли сегодня именинники в классе,
    и рассылает праздничное поздравление в беседы класса в топик «Важные объявления».
    Срабатывает ровно в 00:00 (Asia/Yekaterinburg).
    Для пользователя Исайкин отправляется специальное тройное уведомление с салютами и тортами.
    """
    today = get_today()
    today_str = str(today)

    async with async_session_factory() as session:
        if not force:
            last_sent = await get_class_setting(session, "last_birthday_congratulation_date")
            if last_sent == today_str:
                logger.info(f"Birthday greetings for {today_str} were already sent. Skipping.")
                return 0

        birthday_students = await get_birthdays_for_date(session, today.day, today.month)
        if not birthday_students:
            logger.info(f"No birthdays in class on {today.day}.{today.month}. Marking as checked.")
            await set_class_setting(session, "last_birthday_congratulation_date", today_str)
            return 0

        logger.info(f"Found {len(birthday_students)} birthday celebrant(s) today ({today_str}): {[s.full_name for s in birthday_students]}. Sending greetings...")

        messages_to_send: List[str] = []
        isaykin_students = [s for s in birthday_students if s.full_name.strip().lower() == "исайкин"]
        other_students = [s for s in birthday_students if s.full_name.strip().lower() != "исайкин"]

        if other_students:
            messages_to_send.append(format_birthday_message(other_students, today))

        if isaykin_students:
            # Особенное поздравление для Исайкина: 3 сообщения с эмодзи тортов и фейерверков
            isaykin_msg = "Исайкин с днем рождения!!!! 🎂🍰🎆🎇"
            messages_to_send.extend([isaykin_msg, isaykin_msg, isaykin_msg])

        groups = await get_approved_group_chats(session)
        sent_count = 0

        for g in groups:
            target_thread = g.topic_announcements_id
            kwargs = {"message_thread_id": target_thread} if target_thread else {}
            for text_msg in messages_to_send:
                try:
                    await bot.send_message(
                        chat_id=g.chat_id,
                        text=text_msg,
                        parse_mode="Markdown",
                        **kwargs
                    )
                    sent_count += 1
                    if len(messages_to_send) > 1:
                        await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Could not send birthday greeting to group {g.chat_id} with thread {target_thread}: {e}")
                    if target_thread:
                        try:
                            await bot.send_message(
                                chat_id=g.chat_id,
                                text=text_msg,
                                parse_mode="Markdown"
                            )
                            sent_count += 1
                        except Exception as ex2:
                            logger.error(f"Failed fallback sending birthday greeting to group {g.chat_id}: {ex2}")

        await set_class_setting(session, "last_birthday_congratulation_date", today_str)
        logger.info(f"Birthday greetings successfully sent ({sent_count} msg(s)).")
        return sent_count
