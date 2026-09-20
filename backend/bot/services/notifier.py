import logging
from typing import Optional
from datetime import date, timedelta
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from backend.db.models import Homework
from backend.db.session import async_session_factory
from backend.db.crud import (
    get_notifiable_users, get_homework_for_date,
    get_schedule_for_date, get_bell_schedule_for_date, get_substitutions_for_date,
    get_approved_group_chats, get_current_duty_info, get_class_setting, set_class_setting,
    get_user_homework_status, get_users_in_duty_group
)
from backend.config import get_today
from backend.bot.handlers.schedule import DAYS_RU

logger = logging.getLogger(__name__)

def escape_md(text: str) -> str:
    r"""Экранирует спецсимволы Markdown v1: \, _, *, `, ["""
    if not text:
        return ""
    for ch in ["\\", "_", "*", "`", "["]:
        text = text.replace(ch, f"\\{ch}")
    return text

def format_copyable_desc(desc: str) -> str:
    r"""Форматирует описание ДЗ в отдельный блок для копирования по нажатию в Telegram."""
    if not desc or not desc.strip():
        return "`—`"
    clean = desc.strip().replace("```", "'''").replace("`", "'")
    if "\n" in clean:
        return f"\n```\n{clean}\n```"
    return f"`{clean}`"

async def send_evening_digest(bot: Bot, target_date: Optional[date] = None, force: bool = False) -> int:
    """
    Вечернее персональное напоминание в 19:00:
    Рассылает расписание на завтра и несделанные ДЗ каждому ученику в ЛС
    с учетом его персонального чек-листа (в группы не отправляется).
    Не отправляется по пятницам (на субботу нет ДЗ) и по субботам (на воскресенье).
    """
    logger.info("Executing daily personalized evening digest job...")
    tomorrow = target_date if target_date is not None else (get_today() + timedelta(days=1))

    day_of_week = tomorrow.isoweekday()
    day_name = DAYS_RU.get(day_of_week, "День")
    date_str = tomorrow.strftime("%d.%m.%Y")

    sent_count = 0
    async with async_session_factory() as session:
        schedules = await get_schedule_for_date(session, tomorrow)
        subs = {s.lesson_number: s for s in await get_substitutions_for_date(session, tomorrow)}

        if not force and target_date is None:
            today_weekday = get_today().isoweekday()
            # В субботу вечером (на воскресенье) уроков нет — пропускаем
            if today_weekday == 6 or day_of_week == 7:
                logger.info("Skipping evening digest: tomorrow is Sunday.")
                return 0
            # Если завтра суббота, но уроков нет — пропускаем
            if day_of_week == 6 and not schedules and not subs:
                logger.info("Skipping evening digest: Saturday has no lessons.")
                return 0

        students = await get_notifiable_users(session)
        if not students:
            return 0

        bells = {b.lesson_number: b for b in await get_bell_schedule_for_date(session, tomorrow)}
        tomorrow_homeworks = await get_homework_for_date(session, tomorrow)

        # Другие активные задания на будущие даты после завтра
        res_upcoming = await session.execute(
            select(Homework)
            .options(joinedload(Homework.subject))
            .where(Homework.due_date > tomorrow)
            .order_by(Homework.due_date.asc(), Homework.created_at.desc())
        )
        other_upcoming_homeworks = list(res_upcoming.scalars().all())

        # Формируем строки расписания (одинаковые для всех)
        sched_lines = ["📅 **Расписание уроков:**"]
        if not schedules and not subs:
            sched_lines.append("  _Расписание на завтра не заполнено_")
        else:
            max_l = max([s.lesson_number for s in schedules] + [s.lesson_number for s in subs.values()] or [0])
            sched_map = {s.lesson_number: s for s in schedules}
            for n in range(1, max_l + 1):
                bell = bells.get(n)
                sub = subs.get(n)
                base = sched_map.get(n)

                if base and base.start_time and base.end_time:
                    t_str = f" `{base.start_time}-{base.end_time}`"
                elif bell:
                    t_str = f" `{bell.start_time}-{bell.end_time}`"
                else:
                    t_str = ""

                if sub:
                    if sub.is_cancelled:
                        continue
                    sched_lines.append(f"  {n}.{t_str} {sub.new_subject.name if sub.new_subject else 'Урок'}")
                elif base:
                    sched_lines.append(f"  {n}.{t_str} {base.subject.name}")

            if len(sched_lines) == 1:
                sched_lines.append("  🎉 _На завтра уроков нет!_")

        # 1. Рассылка по группам (с разделением по топикам/веткам)
        approved_groups = await get_approved_group_chats(session)
        sched_group_text = (
            f"📅 **Расписание уроков на завтра ({day_name}, {date_str}):**\n\n"
            + "\n".join(sched_lines[1:] if len(sched_lines) > 1 else sched_lines)
        )
        hw_group_lines = [f"📚 **Домашнее задание на завтра ({day_name}, {date_str}):**\n"]
        if not tomorrow_homeworks:
            hw_group_lines.append("🎉 _Заданий на завтра нет!_")
        else:
            for hw in tomorrow_homeworks:
                hw_group_lines.append(f"• 📌 **{hw.subject.name}:** {format_copyable_desc(hw.description)}")
        hw_group_text = "\n".join(hw_group_lines)

        for g in approved_groups:
            # Если завтра суббота — рассылаем только расписание без ДЗ
            if day_of_week == 6:
                try:
                    await bot.send_message(
                        chat_id=g.chat_id,
                        message_thread_id=g.topic_schedule_id,
                        text=sched_group_text,
                        parse_mode="Markdown"
                    )
                except Exception as e_sc:
                    logger.warning(f"Could not send Saturday schedule to group {g.chat_id}: {e_sc}")
                continue

            # Если настроены отдельные ветки (топики):
            if g.topic_schedule_id or g.topic_hw_id:
                if g.topic_schedule_id:
                    try:
                        await bot.send_message(
                            chat_id=g.chat_id,
                            message_thread_id=g.topic_schedule_id,
                            text=sched_group_text,
                            parse_mode="Markdown"
                        )
                    except Exception as e_sc:
                        logger.warning(f"Could not send schedule to group {g.chat_id} topic {g.topic_schedule_id}: {e_sc}")
                if g.topic_hw_id:
                    try:
                        await bot.send_message(
                            chat_id=g.chat_id,
                            message_thread_id=g.topic_hw_id,
                            text=hw_group_text,
                            parse_mode="Markdown"
                        )
                    except Exception as e_hw:
                        logger.warning(f"Could not send HW to group {g.chat_id} topic {g.topic_hw_id}: {e_hw}")
            else:
                # Общий дайджест в основной поток
                general_digest = (
                    f"🌙 **План на завтра ({day_name}, {date_str}) • 11 «Б»**\n\n"
                    f"{sched_group_text}\n\n"
                    f"{hw_group_text}\n\n"
                    "📱 _Подробнее и вложения — в меню бота и Mini App._"
                )
                try:
                    await bot.send_message(
                        chat_id=g.chat_id,
                        text=general_digest,
                        parse_mode="Markdown"
                    )
                except Exception as e_g:
                    logger.warning(f"Could not send digest to group {g.chat_id}: {e_g}")

        # 2. Рассылка персонально каждому ученику в ЛС
        for st in students:
            if not st.tg_id or st.tg_id <= 0:
                continue
            user_lines = [
                f"🌙 **Добрый вечер, {st.full_name}!**\n",
                f"План на завтра ({day_name}, {date_str}):\n"
            ]
            user_lines.extend(sched_lines)

            # На субботу отправляется только расписание (без блоков ДЗ)
            if day_of_week == 6:
                user_msg = "\n".join(user_lines)
                try:
                    await bot.send_message(chat_id=st.tg_id, text=user_msg, parse_mode="Markdown")
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Could not send evening digest to user {st.tg_id}: {e}")
                continue

            # Проверяем ДЗ на завтра конкретно для этого ученика
            if not tomorrow_homeworks:
                user_lines.append("\n📚 **Домашнее задание на завтра:**")
                user_lines.append("  🎉 _Заданий на завтра нет!_")
            else:
                uncompleted_tomorrow = []
                completed_tomorrow = []
                for hw in tomorrow_homeworks:
                    status = await get_user_homework_status(session, st.id, hw.id)
                    if status and status.is_completed:
                        completed_tomorrow.append(hw)
                    else:
                        uncompleted_tomorrow.append(hw)

                user_lines.append("\n📚 **Домашнее задание на завтра:**")
                if not uncompleted_tomorrow:
                    user_lines.append(f"  🎉 **Все задания на завтра ({len(completed_tomorrow)} из {len(tomorrow_homeworks)}) выполнены! Вы молодец!** ✅")
                else:
                    user_lines.append(f"  _Невыполненные задания ({len(uncompleted_tomorrow)} из {len(tomorrow_homeworks)}):_")
                    for hw in uncompleted_tomorrow:
                        user_lines.append(f"  • 📌 **{hw.subject.name}:** {format_copyable_desc(hw.description)}")
                    if completed_tomorrow:
                        user_lines.append(f"  _(Уже выполнено по чек-листу: {len(completed_tomorrow)})_")

            # Проверяем другие невыполненные ДЗ на ближайшие дни
            uncompleted_other = []
            for hw in other_upcoming_homeworks:
                status = await get_user_homework_status(session, st.id, hw.id)
                if not status or not status.is_completed:
                    uncompleted_other.append(hw)

            if uncompleted_other:
                user_lines.append("\n⏳ **Другие несделанные задания:**")
                for hw in uncompleted_other:
                    d_str = hw.due_date.strftime("%d.%m")
                    user_lines.append(f"  • 📌 **{hw.subject.name}** (к {d_str}): {format_copyable_desc(hw.description)}")

            user_lines.append("\n📱 _Отметить выполнение и посмотреть вложения — в Mini App или меню бота._")
            user_msg = "\n".join(user_lines)

            try:
                await bot.send_message(chat_id=st.tg_id, text=user_msg, parse_mode="Markdown")
                sent_count += 1
            except Exception as e:
                try:
                    plain_msg = user_msg.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
                    await bot.send_message(chat_id=st.tg_id, text=plain_msg, parse_mode=None)
                except Exception as e2:
                    logger.warning(f"Could not send evening digest to user {st.tg_id}: {e2}")

        try:
            await set_class_setting(session, "last_evening_digest_date", str(get_today()))
        except Exception:
            pass

    logger.info(f"Personalized evening digest sent to {sent_count} students in PM.")
    return sent_count


async def send_schedule_change_alert(
    bot: Bot,
    alert_title: str,
    schedule_lines: list[str],
    to_groups: bool = True,
    to_users: bool = True
) -> tuple[int, int]:
    """
    Sends notification about schedule change to students and/or approved groups.
    Returns tuple: (groups_sent, users_sent)
    """
    body = "\n".join(schedule_lines)
    full_msg = (
        f"📢 **ВНИМАНИЕ! ИЗМЕНЕНИЕ В РАСПИСАНИИ**\n"
        f"{alert_title}\n\n"
        f"{body}\n\n"
        f"📱 _Проверить полное расписание можно в Mini App или меню бота._"
    )
    users_sent = 0
    groups_sent = 0
    async with async_session_factory() as session:
        if to_users:
            students = await get_notifiable_users(session)
            for st in students:
                if not st.tg_id or st.tg_id <= 0:
                    continue
                try:
                    await bot.send_message(chat_id=st.tg_id, text=full_msg, parse_mode="Markdown")
                    users_sent += 1
                except Exception as e:
                    logger.warning(f"Could not send schedule alert to user {st.tg_id}: {e}")

        if to_groups:
            groups = await get_approved_group_chats(session)
            for g in groups:
                try:
                    await bot.send_message(
                        chat_id=g.chat_id,
                        message_thread_id=g.topic_schedule_id,
                        text=full_msg,
                        parse_mode="Markdown"
                    )
                    groups_sent += 1
                except Exception as e:
                    logger.warning(f"Could not send schedule alert to group {g.chat_id}: {e}")

    return groups_sent, users_sent


async def send_new_homework_alert(
    bot: Bot,
    session: AsyncSession,
    hw,
    to_group: bool = True,
    to_users: bool = False
) -> tuple[int, int]:
    """
    Рассылает уведомление о новом домашнем задании с прикрепленными фото/файлами.
    Возвращает кортеж (отправлено_в_группы, отправлено_в_лс).
    """
    from aiogram.types import InputMediaPhoto, InputMediaDocument

    day_name = DAYS_RU.get(hw.due_date.isoweekday(), "")
    desc_formatted = format_copyable_desc(hw.description)
    text = (
        f"📚 **НОВОЕ ДОМАШНЕЕ ЗАДАНИЕ • 11 «Б»**\n\n"
        f"📖 **Предмет:** {hw.subject.name if hw.subject else 'Урок'}\n"
        f"📅 **Срок сдачи:** {day_name}, {hw.due_date.strftime('%d.%m.%Y')}\n\n"
        f"📝 **Задание:**\n{desc_formatted}\n\n"
        f"📱 _Чек-лист выполнения и фото доступны в Mini App!_"
    )
    plain_text = (
        f"📚 НОВОЕ ДОМАШНЕЕ ЗАДАНИЕ • 11 «Б»\n\n"
        f"📖 Предмет: {hw.subject.name if hw.subject else 'Урок'}\n"
        f"📅 Срок сдачи: {day_name}, {hw.due_date.strftime('%d.%m.%Y')}\n\n"
        f"📝 Задание:\n{hw.description}\n\n"
        f"📱 Чек-лист выполнения и фото доступны в Mini App!"
    )

    targets = []
    groups_count = 0
    users_count = 0

    if to_group:
        groups = await get_approved_group_chats(session)
        for g in groups:
            targets.append((g.chat_id, "group", g.topic_hw_id))

    if to_users:
        students = await get_notifiable_users(session)
        for st in students:
            if st.tg_id and st.tg_id > 0:
                targets.append((st.tg_id, "user", None))

    photos = [a for a in (hw.attachments or []) if a.get("type") == "photo" and a.get("file_id")]
    docs = [a for a in (hw.attachments or []) if a.get("type") == "document" and a.get("file_id")]

    for chat_id, ctype, thread_id in targets:
        try:
            if photos:
                if len(photos) == 1 and not docs:
                    try:
                        await bot.send_photo(
                            chat_id=chat_id,
                            message_thread_id=thread_id,
                            photo=photos[0]["file_id"],
                            caption=text,
                            parse_mode="Markdown"
                        )
                    except Exception:
                        await bot.send_photo(
                            chat_id=chat_id,
                            message_thread_id=thread_id,
                            photo=photos[0]["file_id"],
                            caption=plain_text,
                            parse_mode=None
                        )
                else:
                    media_group = [
                        InputMediaPhoto(
                            media=p["file_id"],
                            caption=text if i == 0 else None,
                            parse_mode="Markdown" if i == 0 else None
                        )
                        for i, p in enumerate(photos)
                    ]
                    try:
                        await bot.send_media_group(chat_id=chat_id, message_thread_id=thread_id, media=media_group)
                    except Exception:
                        media_group_plain = [
                            InputMediaPhoto(
                                media=p["file_id"],
                                caption=plain_text if i == 0 else None,
                                parse_mode=None
                            )
                            for i, p in enumerate(photos)
                        ]
                        await bot.send_media_group(chat_id=chat_id, message_thread_id=thread_id, media=media_group_plain)

                if docs:
                    if len(docs) == 1:
                        await bot.send_document(
                            chat_id=chat_id,
                            message_thread_id=thread_id,
                            document=docs[0]["file_id"],
                            caption=f"📎 Документ к заданию: {hw.subject.name if hw.subject else ''}"
                        )
                    else:
                        doc_group = [InputMediaDocument(media=d["file_id"]) for d in docs]
                        await bot.send_media_group(chat_id=chat_id, message_thread_id=thread_id, media=doc_group)
            elif docs:
                if len(docs) == 1:
                    try:
                        await bot.send_document(
                            chat_id=chat_id,
                            message_thread_id=thread_id,
                            document=docs[0]["file_id"],
                            caption=text,
                            parse_mode="Markdown"
                        )
                    except Exception:
                        await bot.send_document(
                            chat_id=chat_id,
                            message_thread_id=thread_id,
                            document=docs[0]["file_id"],
                            caption=plain_text,
                            parse_mode=None
                        )
                else:
                    doc_group = [
                        InputMediaDocument(
                            media=d["file_id"],
                            caption=text if i == 0 else None,
                            parse_mode="Markdown" if i == 0 else None
                        )
                        for i, d in enumerate(docs)
                    ]
                    try:
                        await bot.send_media_group(chat_id=chat_id, message_thread_id=thread_id, media=doc_group)
                    except Exception:
                        doc_group_plain = [
                            InputMediaDocument(
                                media=d["file_id"],
                                caption=plain_text if i == 0 else None,
                                parse_mode=None
                            )
                            for i, d in enumerate(docs)
                        ]
                        await bot.send_media_group(chat_id=chat_id, message_thread_id=thread_id, media=doc_group_plain)
            else:
                try:
                    await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=text, parse_mode="Markdown")
                except Exception:
                    await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=plain_text, parse_mode=None)

            if ctype == "group":
                groups_count += 1
            else:
                users_count += 1

        except Exception as e:
            logger.warning(f"Could not send homework alert to {ctype} {chat_id}: {e}")

    return groups_count, users_count


async def notify_duty_change_if_needed(bot: Bot, session: AsyncSession, force: bool = False) -> bool:
    """
    Проверяет, сменилась ли группа дежурных, и отправляет оповещение в чат и ученикам.
    """
    active_group, _ = await get_current_duty_info(session)
    if not active_group:
        return False

    last_notified = await get_class_setting(session, "last_notified_duty_group")
    if not force and last_notified == str(active_group.group_number):
        return False

    await set_class_setting(session, "last_notified_duty_group", str(active_group.group_number))

    members_text = active_group.members if active_group.members and active_group.members != "Состав не назначен" else "Состав уточняется"
    msg = (
        "🧹 **Смена дежурных в 11 «Б»!**\n\n"
        f"📌 **Дежурит:** {active_group.name}\n"
        f"👥 **Состав:** {members_text}\n\n"
        "Пожалуйста, следите за чистотой и порядком в классе!"
    )

    groups = await get_approved_group_chats(session)
    students = await get_notifiable_users(session)

    for g in groups:
        try:
            await bot.send_message(
                chat_id=g.chat_id,
                message_thread_id=g.topic_duty_id,
                text=msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not send duty notification to group {g.chat_id}: {e}")

    for s in students:
        if not s.tg_id or s.tg_id <= 0:
            continue
        try:
            await bot.send_message(chat_id=s.tg_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Could not send duty notification to student {s.tg_id}: {e}")

    # Персональное уведомление дежурным этой группы в ЛС
    duty_users = await get_users_in_duty_group(session, active_group)
    personal_duty_msg = (
        f"🧹 **Внимание! Ваша группа заступает на дежурство!**\n\n"
        f"📌 На этой неделе дежурит **{active_group.name}**, и вы назначены дежурным.\n"
        f"👥 **Состав группы:** {members_text}\n\n"
        "Пожалуйста, не забудьте проветрить класс, подготовить доску и следить за порядком!"
    )
    for u in duty_users:
        if not u.tg_id or u.tg_id <= 0:
            continue
        try:
            await bot.send_message(chat_id=u.tg_id, text=personal_duty_msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Could not send personal duty notification to user {u.tg_id}: {e}")

    return True


async def check_and_send_duty_reminder(bot: Bot):
    """
    Регулярная задача проверки смены группы дежурных (по расписанию крона).
    """
    async with async_session_factory() as session:
        await notify_duty_change_if_needed(bot, session, force=False)


async def send_monday_duty_personal_reminder(bot: Bot):
    """
    Личное напоминание в ЛС дежурным в понедельник в 06:00 утра.
    """
    logger.info("Executing Monday 06:00 personal duty reminder job...")
    async with async_session_factory() as session:
        active_group, _ = await get_current_duty_info(session)
        if not active_group:
            return

        duty_users = await get_users_in_duty_group(session, active_group)
        if not duty_users:
            logger.info("No registered users found in active duty group.")
            return

        members_text = active_group.members if active_group.members and active_group.members != "Состав не назначен" else "Состав уточняется"
        sent_count = 0

        for u in duty_users:
            if not u.tg_id or u.tg_id <= 0:
                continue
            name_greeting = u.display_name
            msg = (
                f"🔔 **Доброе утро, {name_greeting}! Напоминание о дежурстве** 🧹\n\n"
                f"На этой неделе дежурит **{active_group.name}**, и вы входите в её состав!\n\n"
                f"👥 **Состав группы:** {members_text}\n\n"
                "Пожалуйста, не забудьте прийти вовремя, проветрить класс, подготовить доску и следить за порядком."
            )
            try:
                await bot.send_message(chat_id=u.tg_id, text=msg, parse_mode="Markdown")
                sent_count += 1
            except Exception as e:
                logger.warning(f"Could not send Monday duty reminder to {u.tg_id}: {e}")

        logger.info(f"Monday duty personal reminders sent to {sent_count} members.")


async def notify_all_admins(
    bot: Bot,
    session: AsyncSession,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> int:
    """
    Отправляет служебное уведомление (заявки на вход, новые группы и т.д.)
    всем администраторам системы (User.role == 'admin') и главному администратору (ADMIN_ID).
    Возвращает количество успешно доставленных сообщений.
    """
    from backend.config import settings
    from backend.db.crud import get_admin_users

    admin_ids = set()
    if settings.ADMIN_ID:
        admin_ids.add(settings.ADMIN_ID)

    admins = await get_admin_users(session)
    for a in admins:
        if a.tg_id:
            admin_ids.add(a.tg_id)

    sent = 0
    for chat_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to notify admin {chat_id}: {e}")
    return sent






