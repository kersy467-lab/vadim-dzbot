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

router = Router(name='admin_sched_perm_router')

# ==================== PERMANENT SCHEDULE ====================

@router.callback_query(F.data == "admin_edit_schedule")
async def cb_start_edit_schedule(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    days = [("Пн", 1), ("Вт", 2), ("Ср", 3), ("Чт", 4), ("Пт", 5), ("Сб", 6)]
    buttons = []
    current_row = []
    for d_name, d_num in days:
        current_row.append(InlineKeyboardButton(text=d_name, callback_data=f"adm_sc_day_{d_num}"))
        if len(current_row) == 3:
            buttons.append(current_row)
            current_row = []
    if current_row:
        buttons.append(current_row)
    buttons.append([InlineKeyboardButton(text="📅 Скопировать с конкретной даты", callback_data="adm_sc_copy_from_date")])
    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")])

    await state.set_state(EditScheduleStates.choosing_day)
    await callback.message.edit_text(
        "📅 **Редактор расписания уроков:**\n\nВыберите день недели для настройки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_sc_day_"))
async def cb_edit_sched_day_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    day_num = int(callback.data.replace("adm_sc_day_", ""))
    await state.update_data(edit_day=day_num)

    day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота"}
    day_name = day_names.get(day_num, "День")

    items = await get_schedule_for_day(db_session, day_num)
    cur_lines = [f"{it.lesson_number}. {it.subject.name if it.subject else 'Урок'}" for it in items]
    cur_text = "\n".join(cur_lines) if cur_lines else "_Расписание пока не заполнено_"

    btns = [
        [InlineKeyboardButton(text="🎛 Пошаговый конструктор (кнопками)", callback_data="adm_sc_wizard")],
        [InlineKeyboardButton(text="✏️ Ввести весь день текстом (быстро)", callback_data="adm_sc_bulk")],
        [InlineKeyboardButton(text="🔢 Изменить отдельный урок", callback_data="adm_sc_single")],
        [InlineKeyboardButton(text="🔙 Назад к дням", callback_data="admin_edit_schedule")]
    ]

    try:
        await callback.message.edit_text(
            f"🗓 **Постоянное расписание — {day_name}:**\n\n"
            f"{cur_text}\n\n"
            "Выберите способ редактирования:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_sc_bulk")
async def cb_edit_sched_bulk_prompt(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    day_num = data.get("edit_day", 1)
    day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота"}
    day_name = day_names.get(day_num, "день")

    await state.set_state(EditScheduleStates.entering_text_bulk)
    await callback.message.edit_text(
        f"✏️ **Введите постоянное расписание на {day_name} одним сообщением:**\n\n"
        "Каждый урок пишите с новой строки. Новые предметы добавятся автоматически.\n\n"
        "**Пример:**\n"
        "`1. Алгебра`\n"
        "`2. Русский язык`\n"
        "`3. Физика`\n"
        "`4. Химия`\n"
        "`5. Литература`\n"
        "`6. Физкультура`\n"
        "`7. Английский язык`\n\n"
        "Отправьте текст в ответ на это сообщение 👇",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(EditScheduleStates.entering_text_bulk)
async def msg_edit_sched_bulk_save(message: Message, state: FSMContext, db_session: AsyncSession):
    lessons = parse_schedule_text(message.text)
    if not lessons:
        await message.answer(
            "⚠️ Не удалось распознать уроки. Отправьте список уроков построчно:\n\n"
            "1. Алгебра\n2. Физика\n3. Русский язык"
        )
        return

    data = await state.get_data()
    day_num = data.get("edit_day", 1)
    day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота"}
    day_name = day_names.get(day_num, "день")

    saved_items = await save_bulk_permanent_schedule(db_session, day_num, lessons)
    await auto_shift_active_homeworks(db_session)
    lines = [f"  {l_num}. {s_name}" for l_num, s_name in lessons]

    await state.clear()
    await message.answer(
        f"✅ **Постоянное расписание на {day_name} успешно сохранено ({len(saved_items)} ур.)!**\n\n" +
        "\n".join(lines),
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "adm_sc_single")
async def cb_edit_sched_single_lessons(callback: CallbackQuery, state: FSMContext):
    btns = [
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_sc_l_{i}") for i in range(1, 5)],
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_sc_l_{i}") for i in range(5, 9)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_edit_schedule")]
    ]
    await state.set_state(EditScheduleStates.choosing_lesson)
    await callback.message.edit_text(
        "Какой по счету урок вы хотите изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_sc_l_"))
async def cb_edit_sched_lesson_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    l_num = int(callback.data.replace("adm_sc_l_", ""))
    await state.update_data(edit_lesson=l_num)

    subjects = await get_all_subjects(db_session)
    btns = [[InlineKeyboardButton(text=s.name, callback_data=f"adm_sc_subj_{s.id}")] for s in subjects]
    btns.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])

    await state.set_state(EditScheduleStates.choosing_subject)
    await callback.message.edit_text(
        f"📖 **Выберите предмет для {l_num}-го урока:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_sc_subj_"))
async def cb_edit_sched_save(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    subj_id = int(callback.data.replace("adm_sc_subj_", ""))
    data = await state.get_data()
    day_num = data["edit_day"]
    l_num = data["edit_lesson"]

    await set_permanent_schedule_item(
        session=db_session,
        day_of_week=day_num,
        lesson_number=l_num,
        subject_id=subj_id
    )
    await auto_shift_active_homeworks(db_session)

    subj = await get_subject_by_id(db_session, subj_id)
    day_names = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб"}

    await state.clear()
    await callback.message.edit_text(
        f"✅ **Постоянное расписание обновлено!**\n\n"
        f"📅 **День:** {day_names.get(day_num, '')}\n"
        f"🔢 **Урок:** {l_num}-й\n"
        f"📖 **Предмет:** {subj.name if subj else ''}",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сохранено!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_sc_copy_from_date")
async def cb_start_copy_from_date(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    today = date.today()
    kb = get_inline_calendar("adm_sccpy", year=today.year, month=today.month, back_callback="admin_edit_schedule")
    await callback.message.edit_text(
        "📅 **Копирование расписания с даты:**\n\n"
        "Выберите дату, расписание которой нужно сохранить как постоянное (для соответствующего дня недели):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_nav_adm_sccpy_"))
async def cb_cal_nav_adm_sccpy(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    kb = get_inline_calendar("adm_sccpy", year=year, month=month, back_callback="admin_edit_schedule")
    await callback.message.edit_text(
        "📅 **Копирование расписания с даты:**\n\n"
        "Выберите дату, расписание которой нужно сохранить как постоянное (для соответствующего дня недели):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_act_adm_sccpy_"))
async def cb_cal_act_adm_sccpy(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    day = int(parts[6])
    target_d = date(year, month, day)

    lessons = await get_schedule_for_date(db_session, target_d)
    if not lessons:
        await callback.answer("На выбранную дату нет уроков для копирования!", show_alert=True)
        return

    day_num = target_d.isoweekday()
    day_name = DAYS_RU.get(day_num, "день")

    lessons_tuples = [(l.lesson_number, l.subject.name) for l in lessons]
    await save_bulk_permanent_schedule(db_session, day_num, lessons_tuples)
    await auto_shift_active_homeworks(db_session)

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
        await callback.answer("Расписание скопировано в постоянное!")
    except Exception:
        pass



