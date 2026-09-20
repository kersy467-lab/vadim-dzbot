from datetime import date, timedelta
from typing import List, Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_today, settings
from backend.db.models import User

def is_admin_user(user: Optional[User], tg_id: int) -> bool:
    if settings.ADMIN_ID and tg_id == settings.ADMIN_ID:
        return True
    return user is not None and user.role == "admin"

from backend.db.crud import (
    get_schedule_for_day, get_schedule_for_date, get_bell_schedule, get_bell_schedule_for_date,
    get_substitutions_for_date, get_full_week_schedule, get_current_duty_info
)

from backend.bot.keyboards.inline import (
    get_schedule_keyboard, get_day_picker_keyboard
)

router = Router(name="schedule_router")

DAYS_RU = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье"
}

from backend.bot.services.academic_calendar import get_day_special_status

async def format_day_schedule(session: AsyncSession, target_date: date) -> str:
    day_of_week = target_date.isoweekday() # 1 = Monday, 7 = Sunday
    day_name = DAYS_RU.get(day_of_week, "День")
    date_str = target_date.strftime("%d.%m.%Y")

    status, status_text = get_day_special_status(target_date)

    if target_date <= date(2026, 9, 1):
        if target_date == date(2026, 9, 1):
            return f"🔔 **{day_name} ({date_str}) • 11 «Б»**\n\n🎉 **{status_text}!**\nТоржественная линейка и классный час — уроков не было."
        return f"🌴 **{day_name} ({date_str}) • 11 «Б»**\n\n🎉 **{status_text}!**\nУроков нет, приятного отдыха!"

    if status == "vacation":
        return f"🌴 **{day_name} ({date_str}) • 11 «Б»**\n\n🎉 **{status_text}!**\nУроков нет, приятного отдыха!"

    schedules = await get_schedule_for_date(session, target_date)

    subs = {s.lesson_number: s for s in await get_substitutions_for_date(session, target_date)}

    if status == "weekend" and not subs and not schedules:
        return f"🏖 **{day_name} ({date_str}) • 11 «Б»**\n\n{status_text} — уроков нет, отдыхаем!"

    bells = {b.lesson_number: b for b in await get_bell_schedule_for_date(session, target_date)}


    if not schedules and not subs:
        return f"📅 **{day_name} ({date_str}) • 11 «Б»**\n\nРасписание на этот день пока не заполнено."

    header_extra = f" *(Рабочая суббота — перенос уроков)*" if status == "working_weekend" else ""
    text_lines = [f"📅 **Расписание 11 «Б» на {day_name} ({date_str}):**{header_extra}\n"]


    max_lesson = max(
        [s.lesson_number for s in schedules] + [s.lesson_number for s in subs.values()] or [0]
    )

    sched_map = {s.lesson_number: s for s in schedules}

    for num in range(1, max_lesson + 1):
        bell = bells.get(num)
        base = sched_map.get(num)
        sub = subs.get(num)

        if base and base.start_time and base.end_time:
            time_str = f" `{base.start_time}-{base.end_time}`"
        elif bell:
            time_str = f" `{bell.start_time}-{bell.end_time}`"
        else:
            time_str = ""

        if sub:
            if sub.is_cancelled:
                continue
            new_name = sub.new_subject.name if sub.new_subject else (base.subject.name if base else "Урок")
            comment = f" — *{sub.comment}*" if sub.comment else ""
            text_lines.append(f"**{num}.**{time_str} {new_name}{comment}")
        elif base:
            text_lines.append(f"**{num}.**{time_str} {base.subject.name}")

    if len(text_lines) == 1:
        text_lines.append("🎉 _На этот день уроков нет!_")

    return "\n".join(text_lines)

@router.message(F.text == "📅 Расписание")
async def show_schedule_menu(message: Message, db_session: AsyncSession, current_user: Optional[User] = None):
    today = date.today()
    schedule_text = await format_day_schedule(db_session, today)
    is_adm = is_admin_user(current_user, message.from_user.id) if current_user else False
    await message.answer(
        schedule_text,
        reply_markup=get_schedule_keyboard(is_admin=is_adm),
        parse_mode="Markdown"
    )

def format_bell_schedule_text(bells: list) -> str:
    lines = ["🔔 **Расписание звонков:**\n"]
    for b in bells:
        break_str = f" *({b.break_duration} мин.)*" if b.break_duration else ""
        lines.append(f"**{b.lesson_number} урок**  `{b.start_time} – {b.end_time}` {break_str}")
    return "\n".join(lines)

@router.message(F.text == "🔔 Звонки")

async def show_bells(message: Message, db_session: AsyncSession):
    bells = await get_bell_schedule_for_date(db_session, get_today())
    if not bells:
        await message.answer("🔔 Расписание звонков пока не заполнено.")
        return

    await message.answer(format_bell_schedule_text(bells), parse_mode="Markdown")

async def safe_edit_schedule_message(
    callback: CallbackQuery,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "Markdown",
    same_message_alert: str = "Расписание уже открыто 📅"
) -> None:
    """Безопасно редактирует сообщение с расписанием, предотвращая ошибку 'message is not modified'."""
    try:
        if callback.message:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        await callback.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            await callback.answer(same_message_alert)
        else:
            raise e

@router.callback_query(F.data == "sched_today")
async def cb_sched_today(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    text = await format_day_schedule(db_session, get_today())
    is_adm = is_admin_user(current_user, callback.from_user.id) if current_user else False
    await safe_edit_schedule_message(callback, text, reply_markup=get_schedule_keyboard(is_admin=is_adm), same_message_alert="Расписание на сегодня уже открыто 📅")

@router.callback_query(F.data == "sched_tomorrow")
async def cb_sched_tomorrow(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    tomorrow = get_today() + timedelta(days=1)
    text = await format_day_schedule(db_session, tomorrow)
    is_adm = is_admin_user(current_user, callback.from_user.id) if current_user else False
    await safe_edit_schedule_message(callback, text, reply_markup=get_schedule_keyboard(is_admin=is_adm), same_message_alert="Расписание на завтра уже открыто 📅")

@router.callback_query(F.data == "sched_bells")
async def cb_sched_bells(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    bells = await get_bell_schedule_for_date(db_session, get_today())
    if not bells:
        await callback.answer("Расписание звонков не заполнено", show_alert=True)
        return

    text = format_bell_schedule_text(bells)
    is_adm = is_admin_user(current_user, callback.from_user.id) if current_user else False
    await safe_edit_schedule_message(callback, text, reply_markup=get_schedule_keyboard(is_admin=is_adm), same_message_alert="Расписание звонков уже открыто 🔔")


from backend.bot.keyboards.calendar import get_inline_calendar

@router.callback_query(F.data == "cal_ignore")
async def cb_cal_ignore(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "sched_calendar")
async def cb_sched_calendar(callback: CallbackQuery):
    today = get_today()
    kb = get_inline_calendar("sched", year=today.year, month=today.month, back_callback="sched_menu")
    await callback.message.edit_text(
        "🗓 **Выберите дату на календаре:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cal_nav_sched_"))
async def cb_cal_nav_sched(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[3])
    month = int(parts[4])
    kb = get_inline_calendar("sched", year=year, month=month, back_callback="sched_menu")
    await callback.message.edit_text(
        "🗓 **Выберите дату на календаре:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cal_act_sched_"))
async def cb_cal_act_sched(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    parts = callback.data.split("_")
    year = int(parts[3])
    month = int(parts[4])
    day = int(parts[5])
    target_date = date(year, month, day)

    text = await format_day_schedule(db_session, target_date)
    is_adm = is_admin_user(current_user, callback.from_user.id) if current_user else False
    await safe_edit_schedule_message(callback, text, reply_markup=get_schedule_keyboard(is_admin=is_adm))

@router.callback_query(F.data == "sched_pick_day")
async def cb_sched_pick_day(callback: CallbackQuery):
    await callback.message.edit_text(
        "🗓 Выберите день недели:",
        reply_markup=get_day_picker_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("sched_day_"))
async def cb_sched_day_selected(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    day_num = int(callback.data.replace("sched_day_", ""))
    today = get_today()
    current_day = today.isoweekday()
    delta_days = (day_num - current_day) % 7
    target_date = today + timedelta(days=delta_days)

    text = await format_day_schedule(db_session, target_date)
    is_adm = is_admin_user(current_user, callback.from_user.id) if current_user else False
    await safe_edit_schedule_message(callback, text, reply_markup=get_schedule_keyboard(is_admin=is_adm))

@router.callback_query(F.data == "sched_week")
async def cb_sched_week(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    week_schedule = await get_full_week_schedule(db_session)
    bells = {b.lesson_number: b for b in await get_bell_schedule(db_session)}

    text_parts = ["📅 **Расписание 11 «Б» на всю неделю:**\n"]

    for day_num in range(1, 7):
        day_name = DAYS_RU.get(day_num, "")
        items = week_schedule.get(day_num, [])
        if not items:
            continue
        text_parts.append(f"📌 **{day_name}:**")
        for it in items:
            if it.start_time and it.end_time:
                t_str = f" `{it.start_time}-{it.end_time}`"
            elif it.start_time:
                t_str = f" `{it.start_time}`"
            else:
                bell = bells.get(it.lesson_number)
                t_str = f" `{bell.start_time}`" if bell else ""
            text_parts.append(f"  {it.lesson_number}.{t_str} {it.subject.name}")
        text_parts.append("")

    full_text = "\n".join(text_parts) if len(text_parts) > 1 else "Расписание на неделю пока не заполнено."
    is_adm = is_admin_user(current_user, callback.from_user.id) if current_user else False
    await safe_edit_schedule_message(callback, full_text, reply_markup=get_schedule_keyboard(is_admin=is_adm), same_message_alert="Расписание на неделю уже открыто 📅")

@router.callback_query(F.data == "sched_menu")
async def cb_sched_menu(callback: CallbackQuery, db_session: AsyncSession, current_user: Optional[User] = None):
    text = await format_day_schedule(db_session, get_today())
    is_adm = is_admin_user(current_user, callback.from_user.id) if current_user else False
    await safe_edit_schedule_message(callback, text, reply_markup=get_schedule_keyboard(is_admin=is_adm))


# ==================== SUMMER COUNTDOWN ====================
@router.message(F.text == "☀️ До лета осталось")
async def show_summer_countdown(message: Message):
    today = get_today()
    summer_start = date(2027, 5, 27)
    school_start = date(2026, 9, 1)


    if today >= summer_start:
        await message.answer("🎉 **Ура! Летние каникулы уже наступили!** 🏖🌴", parse_mode="Markdown")
        return

    days_left = (summer_start - today).days
    weeks_left = days_left // 7

    total_school_days = (summer_start - school_start).days
    days_passed = max(0, (today - school_start).days)
    pct = min(100, int((days_passed / total_school_days) * 100))

    filled = pct // 10
    empty = 10 - filled
    progress_bar = "█" * filled + "░" * empty

    text = (
        "☀️ **До лета осталось:**\n\n"
        f"⏳ **{days_left} дней**\n"
        f"📚 **{weeks_left} учебных недель**\n\n"
        f"Прогресс учебного года:\n"
        f"`[{progress_bar}]` **{pct}%** позади\n\n"
        "🌴 *Летние каникулы начнутся 27 мая 2027 года! Отличной учебы и хорошего настроения!*"
    )
    await message.answer(text, parse_mode="Markdown")


# ==================== DUTY ROSTER ====================
@router.message(F.text == "🧹 График дежурств")
async def show_duty_roster(message: Message, db_session: AsyncSession):

    active_group, all_groups = await get_current_duty_info(db_session)

    if not all_groups:
        await message.answer("🧹 Список дежурных групп пока не настроен.", parse_mode="Markdown")
        return

    text_lines = ["🧹 **График дежурств 11 «Б»:**\n"]

    if active_group:
        text_lines.append(f"⭐ **Сейчас дежурит:** **{active_group.name}**")
        text_lines.append(f"👥 **Состав:** {active_group.members}\n")

    text_lines.append("📋 **Все дежурные группы класса:**")
    for g in all_groups:
        badge = " *(дежурит сейчас)* 👈" if active_group and g.group_number == active_group.group_number else ""
        text_lines.append(f"• **{g.name}:** {g.members}{badge}")

    text_lines.append("\n_Дежурство меняется автоматически каждую неделю_")
    await message.answer("\n".join(text_lines), parse_mode="Markdown")





