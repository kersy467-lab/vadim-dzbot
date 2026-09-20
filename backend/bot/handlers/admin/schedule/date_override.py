from datetime import date, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_today
from backend.db.models import User
from backend.db.crud import (
    get_all_subjects, get_subject_by_id,
    set_schedule_item, set_date_schedule_item, set_permanent_schedule_item,
    get_schedule_for_date, get_schedule_for_day,
    save_bulk_date_schedule, save_bulk_permanent_schedule, clear_date_schedule,
    auto_shift_active_homeworks, create_substitution,
    get_notifiable_users, get_approved_group_chats
)
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_notify_confirm_keyboard,
    get_date_schedule_notify_keyboard, get_schedule_broadcast_day_keyboard,
    get_schedule_broadcast_destination_keyboard
)
from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.services.notifier import send_schedule_change_alert
from backend.bot.handlers.schedule import DAYS_RU, format_day_schedule
from backend.bot.handlers.admin.helpers import is_admin, parse_schedule_text
from backend.bot.handlers.admin.states import (
    EditScheduleStates, EditDateScheduleStates, AddSubstitutionStates,
    ScheduleWizardStates, ScheduleBroadcastStates
)

router = Router(name='admin_sched_date_router')

# ==================== DATE-SPECIFIC SCHEDULE ====================

@router.callback_query(F.data == "admin_edit_date_schedule")
async def cb_start_edit_date_schedule(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    today = date.today()
    kb = get_inline_calendar("adm_dtsched", year=today.year, month=today.month, back_callback="admin_menu_back")

    await state.set_state(EditDateScheduleStates.choosing_date)
    await callback.message.edit_text(
        "📅 **Расписание на конкретную дату:**\n\n"
        "Выберите дату в календаре для настройки уроков:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(EditDateScheduleStates.choosing_date, F.data.startswith("cal_nav_adm_dtsched_"))
async def cb_cal_nav_adm_dtsched(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    kb = get_inline_calendar("adm_dtsched", year=year, month=month, back_callback="admin_menu_back")
    await callback.message.edit_text(
        "📅 **Расписание на конкретную дату:**\n\n"
        "Выберите дату в календаре для настройки уроков:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_act_adm_dtsched_"))
async def cb_cal_act_adm_dtsched(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    day = int(parts[6])
    target_d = date(year, month, day)

    await state.update_data(edit_target_date=target_d.isoformat())

    lessons = await get_schedule_for_date(db_session, target_d)
    lesson_lines = [f"{l.lesson_number}. {l.subject.name}" for l in lessons]
    lessons_str = "\n".join(lesson_lines) if lesson_lines else "_Уроки еще не назначены_"

    day_name = DAYS_RU.get(target_d.isoweekday(), "День")
    date_formatted = target_d.strftime("%d.%m.%Y")

    btns = [
        [InlineKeyboardButton(text="🎛 Пошаговый конструктор (кнопками)", callback_data="adm_dt_wizard")],
        [InlineKeyboardButton(text="✏️ Ввести весь день текстом (быстро)", callback_data="adm_dt_bulk")],
        [InlineKeyboardButton(text="🔢 Изменить отдельный урок", callback_data="adm_dt_single")],
        [InlineKeyboardButton(text="📌 Сделать это расписание постоянным", callback_data="adm_dt_make_permanent")],
        [InlineKeyboardButton(text="🗑 Сбросить (к постоянному)", callback_data="adm_dt_reset")],
        [InlineKeyboardButton(text="🔙 К выбору даты", callback_data="admin_edit_date_schedule")]
    ]

    await callback.message.edit_text(
        f"📅 **Расписание на {day_name} ({date_formatted}):**\n\n"
        f"{lessons_str}\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_dt_make_permanent")
async def cb_edit_dt_sched_make_permanent(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    target_d_str = data.get("edit_target_date")
    if not target_d_str:
        await callback.answer("Выберите дату заново", show_alert=True)
        return
    target_d = date.fromisoformat(target_d_str)
    day_num = target_d.isoweekday()
    day_name = DAYS_RU.get(day_num, "день")

    lessons = await get_schedule_for_date(db_session, target_d)
    if not lessons:
        await callback.answer("На эту дату нет уроков для сохранения!", show_alert=True)
        return

    lessons_tuples = [(l.lesson_number, l.subject.name) for l in lessons]
    await save_bulk_permanent_schedule(db_session, day_num, lessons_tuples)
    await clear_date_schedule(db_session, target_d)

    lesson_lines = [f"{l.lesson_number}. {l.subject.name}" for l in lessons]
    lessons_str = "\n".join(lesson_lines)

    await state.clear()
    await callback.message.edit_text(
        f"✅ **Расписание с даты {target_d.strftime('%d.%m.%Y')} успешно установлено как постоянное на каждый {day_name}!**\n\n"
        f"🗓 **Постоянные уроки ({day_name}):**\n"
        f"{lessons_str}\n\n"
        f"_Теперь это расписание действует на все недели вперед как постоянное._",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Установлено как постоянное!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_dt_bulk")
async def cb_edit_dt_sched_bulk_prompt(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target_d_str = data.get("edit_target_date")
    if not target_d_str:
        await callback.answer("Выберите дату заново", show_alert=True)
        return
    target_d = date.fromisoformat(target_d_str)
    day_name = DAYS_RU.get(target_d.isoweekday(), "")

    await state.set_state(EditDateScheduleStates.entering_text_bulk)
    await callback.message.edit_text(
        f"✏️ **Введите расписание на {day_name} ({target_d.strftime('%d.%m.%Y')}) одним сообщением:**\n\n"
        "Каждый урок пишите с новой строки. Новые предметы создадутся автоматически.\n\n"
        "**Пример сообщения:**\n"
        "`1. География`\n"
        "`2. История`\n"
        "`3. Обществознание`\n"
        "`4. Английский язык`\n"
        "`5. Алгебра`\n"
        "`6. Физика`\n\n"
        "Отправьте текст в ответ на это сообщение 👇",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(EditDateScheduleStates.entering_text_bulk)
async def msg_edit_dt_sched_bulk_save(message: Message, state: FSMContext, db_session: AsyncSession):
    lessons = parse_schedule_text(message.text)
    if not lessons:
        await message.answer(
            "⚠️ Не удалось распознать уроки. Отправьте список уроков построчно:\n\n"
            "1. Алгебра\n2. Физика\n3. Русский язык"
        )
        return

    data = await state.get_data()
    target_d = date.fromisoformat(data["edit_target_date"])
    day_name = DAYS_RU.get(target_d.isoweekday(), "")

    saved_items = await save_bulk_date_schedule(db_session, target_d, lessons)
    await auto_shift_active_homeworks(db_session)
    schedule_lines = [f"{l_num}. {s_name}" for l_num, s_name in lessons]

    await state.update_data(
        alert_title=f"📅 **{day_name} ({target_d.strftime('%d.%m.%Y')}):**",
        alert_lines=schedule_lines
    )
    await state.set_state(EditDateScheduleStates.confirm_notification)

    await message.answer(
        f"✅ **Расписание на {day_name} ({target_d.strftime('%d.%m.%Y')}) сохранено ({len(saved_items)} ур.)!**\n\n" +
        "\n".join(schedule_lines) + "\n\n" +
        "📢 **Разослать оповещение классу об изменении расписания?**",
        reply_markup=get_date_schedule_notify_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "adm_dt_single")
async def cb_edit_dt_sched_single_pick(callback: CallbackQuery, state: FSMContext):
    btns = [
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_dt_l_{i}") for i in range(1, 5)],
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_dt_l_{i}") for i in range(5, 9)],
        [InlineKeyboardButton(text="🔙 К выбору даты", callback_data="admin_edit_date_schedule")]
    ]
    await state.set_state(EditDateScheduleStates.choosing_lesson)
    await callback.message.edit_text(
        "Какой урок хотите назначить/изменить на эту дату?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_dt_l_"))
async def cb_edit_dt_sched_lesson_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    l_num = int(callback.data.replace("adm_dt_l_", ""))
    await state.update_data(edit_target_lesson=l_num)

    subjects = await get_all_subjects(db_session)
    btns = [[InlineKeyboardButton(text=s.name, callback_data=f"adm_dt_s_{s.id}")] for s in subjects]
    btns.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])

    await state.set_state(EditDateScheduleStates.choosing_subject)
    await callback.message.edit_text(
        f"📖 **Выберите предмет для {l_num}-го урока на эту дату:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_dt_s_"))
async def cb_edit_dt_sched_save(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    subj_id = int(callback.data.replace("adm_dt_s_", ""))
    data = await state.get_data()
    target_d = date.fromisoformat(data["edit_target_date"])
    l_num = data["edit_target_lesson"]

    await set_date_schedule_item(
        session=db_session,
        target_date=target_d,
        lesson_number=l_num,
        subject_id=subj_id
    )
    await auto_shift_active_homeworks(db_session)

    subj = await get_subject_by_id(db_session, subj_id)
    day_name = DAYS_RU.get(target_d.isoweekday(), "")

    lessons = await get_schedule_for_date(db_session, target_d)
    schedule_lines = [f"{l.lesson_number}. {l.subject.name}" for l in lessons]

    await state.update_data(
        alert_title=f"📅 **{day_name} ({target_d.strftime('%d.%m.%Y')}):**\n_(Изменен {l_num} урок: {subj.name if subj else ''})_",
        alert_lines=schedule_lines
    )
    await state.set_state(EditDateScheduleStates.confirm_notification)

    await callback.message.edit_text(
        f"✅ **Урок на дату сохранен!**\n\n"
        f"📅 **Дата:** {target_d.strftime('%d.%m.%Y')} ({day_name})\n"
        f"🔢 **Урок:** {l_num}-й\n"
        f"📖 **Предмет:** {subj.name if subj else ''}\n\n"
        "📢 **Разослать оповещение классу об изменении расписания?**",
        reply_markup=get_date_schedule_notify_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сохранено!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_dt_reset")
async def cb_edit_dt_sched_reset(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    target_d_str = data.get("edit_target_date")
    if not target_d_str:
        await callback.answer("Выберите дату заново", show_alert=True)
        return
    target_d = date.fromisoformat(target_d_str)
    day_name = DAYS_RU.get(target_d.isoweekday(), "")

    await clear_date_schedule(db_session, target_d)
    await auto_shift_active_homeworks(db_session)

    perm_lessons = await get_schedule_for_date(db_session, target_d)
    schedule_lines = [f"{l.lesson_number}. {l.subject.name}" for l in perm_lessons]

    await state.update_data(
        alert_title=f"📅 **{day_name} ({target_d.strftime('%d.%m.%Y')}):**\n_(Расписание возвращено к стандартному)_",
        alert_lines=schedule_lines
    )
    await state.set_state(EditDateScheduleStates.confirm_notification)

    await callback.message.edit_text(
        f"🗑 **Расписание на {target_d.strftime('%d.%m.%Y')} сброшено к постоянному!**\n\n"
        "📢 **Оповестить класс о возврате к стандартному расписанию?**",
        reply_markup=get_date_schedule_notify_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сброшено!")
    except Exception:
        pass


@router.callback_query(F.data.in_(["adm_dt_notify_groups", "adm_dt_notify_pm", "adm_dt_notify_all", "adm_dt_notify_yes"]))
async def cb_edit_dt_notify_yes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    title = data.get("alert_title", "Изменение расписания")
    lines = data.get("alert_lines", [])

    to_groups = callback.data in ("adm_dt_notify_groups", "adm_dt_notify_all", "adm_dt_notify_yes")
    to_users = callback.data in ("adm_dt_notify_pm", "adm_dt_notify_all", "adm_dt_notify_yes")

    await send_schedule_change_alert(bot, title, lines, to_groups=to_groups, to_users=to_users)
    await state.clear()
    dest_text = "в чат и в ЛС" if (to_groups and to_users) else ("в чат" if to_groups else "в ЛС")
    await callback.message.edit_text(
        f"📢 **Оповещение об изменении расписания успешно разослано ({dest_text})!**",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Разослано!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_dt_notify_no")
async def cb_edit_dt_notify_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🔇 **Изменения сохранены без рассылки оповещения.**",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сохранено!")
    except Exception:
        pass


