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

router = Router(name='admin_sched_wiz_router')

# ==================== STEP-BY-STEP SCHEDULE WIZARD ====================

@router.callback_query(F.data == "adm_sc_wizard")
async def cb_start_schedule_wizard_permanent(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    day_num = data.get("edit_day", 1)
    day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота"}
    day_name = day_names.get(day_num, "день")

    await state.update_data(wizard_mode="permanent", wizard_lessons={})
    await state.set_state(ScheduleWizardStates.choosing_lesson_count)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{i}", callback_data=f"wiz_cnt_{i}") for i in range(1, 5)],
            [InlineKeyboardButton(text=f"{i}", callback_data=f"wiz_cnt_{i}") for i in range(5, 9)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )

    await callback.message.edit_text(
        f"🎛 **Конструктор постоянного расписания на {day_name}**\n\n"
        "🔢 **Сколько всего уроков будет в этот день?**\n"
        "Нажмите кнопку с нужным количеством уроков (от 1 до 8):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_dt_wizard")
async def cb_start_schedule_wizard_date(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target_d = date.fromisoformat(data["edit_target_date"])
    day_name = DAYS_RU.get(target_d.isoweekday(), "")

    await state.update_data(wizard_mode="date", wizard_lessons={})
    await state.set_state(ScheduleWizardStates.choosing_lesson_count)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{i}", callback_data=f"wiz_cnt_{i}") for i in range(1, 5)],
            [InlineKeyboardButton(text=f"{i}", callback_data=f"wiz_cnt_{i}") for i in range(5, 9)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )

    await callback.message.edit_text(
        f"🎛 **Конструктор расписания на {day_name} ({target_d.strftime('%d.%m.%Y')})**\n\n"
        "🔢 **Сколько всего уроков будет в этот день?**\n"
        "Нажмите кнопку с нужным количеством уроков (от 1 до 8):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


async def render_wizard_lesson_step(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    total = data["wizard_total"]
    cur = data["wizard_cur"]
    lessons = data.get("wizard_lessons", {})

    mode = data.get("wizard_mode")
    if mode == "permanent":
        day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота"}
        day_str = f"Постоянное — {day_names.get(data.get('edit_day', 1), '')}"
    else:
        target_d = date.fromisoformat(data["edit_target_date"])
        day_str = f"{DAYS_RU.get(target_d.isoweekday(), '')} ({target_d.strftime('%d.%m.%Y')})"

    preview_lines = []
    for i in range(1, cur):
        name = lessons.get(str(i)) or lessons.get(i)
        val = f"**{name}**" if name else "_— (прочерк / окно)_"
        preview_lines.append(f"  {i}. {val}")
    preview_lines.append(f"👉 **{cur}. [Выбирается сейчас...]**")

    subjects = await get_all_subjects(db_session)
    buttons = []
    row = []
    for s in subjects:
        row.append(InlineKeyboardButton(text=s.name, callback_data=f"wiz_sub_s_{s.id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    ctrl_row = [
        InlineKeyboardButton(text="➖ Прочерк / Окно", callback_data="wiz_sub_skip")
    ]
    if cur > 1:
        ctrl_row.append(InlineKeyboardButton(text="💾 Завершить сейчас", callback_data="wiz_sub_finish"))
    buttons.append(ctrl_row)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])

    text = (
        f"🎛 **Конструктор расписания ({day_str})**\n"
        f"📌 **Шаг {cur} из {total}:** выбор предмета для **{cur}-го урока**\n\n"
        + "\n".join(preview_lines) + "\n\n"
        "Нажмите на кнопку предмета или «➖ Прочерк / Окно»:"
    )

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


@router.callback_query(F.data.startswith("wiz_cnt_"))
async def cb_wizard_count_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    cnt = int(callback.data.replace("wiz_cnt_", ""))
    await state.update_data(wizard_total=cnt, wizard_cur=1, wizard_lessons={})
    await state.set_state(ScheduleWizardStates.choosing_subject_for_lesson)
    await render_wizard_lesson_step(callback, state, db_session)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("wiz_sub_s_"))
async def cb_wizard_subject_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    subj_id = int(callback.data.replace("wiz_sub_s_", ""))
    subj = await get_subject_by_id(db_session, subj_id)
    subj_name = subj.name if subj else "Предмет"

    data = await state.get_data()
    cur = data.get("wizard_cur", 1)
    total = data.get("wizard_total", 8)
    lessons = data.get("wizard_lessons", {})
    lessons[str(cur)] = subj_name

    cur += 1
    await state.update_data(wizard_cur=cur, wizard_lessons=lessons)

    if cur <= total:
        await render_wizard_lesson_step(callback, state, db_session)
    else:
        await finalize_schedule_wizard(callback, state, db_session)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "wiz_sub_skip")
async def cb_wizard_subject_skip(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    cur = data.get("wizard_cur", 1)
    total = data.get("wizard_total", 8)
    lessons = data.get("wizard_lessons", {})
    lessons[str(cur)] = None

    cur += 1
    await state.update_data(wizard_cur=cur, wizard_lessons=lessons)

    if cur <= total:
        await render_wizard_lesson_step(callback, state, db_session)
    else:
        await finalize_schedule_wizard(callback, state, db_session)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "wiz_sub_finish")
async def cb_wizard_subject_finish_early(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    await finalize_schedule_wizard(callback, state, db_session)
    try:
        await callback.answer()
    except Exception:
        pass


async def finalize_schedule_wizard(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    lessons = data.get("wizard_lessons", {})
    mode = data.get("wizard_mode")

    final_lessons = []
    lines = []
    total = data.get("wizard_total", max([int(k) for k in lessons.keys()] or [0]))
    for i in range(1, total + 1):
        name = lessons.get(str(i)) or lessons.get(i)
        if name:
            final_lessons.append((i, name))
            lines.append(f"  {i}. **{name}**")
        else:
            lines.append(f"  {i}. _— (окно / нет урока)_")

    if mode == "permanent":
        day_num = data["edit_day"]
        day_names = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница", 6: "Суббота"}
        day_name = day_names.get(day_num, "день")

        saved = await save_bulk_permanent_schedule(db_session, day_num, final_lessons)
        await auto_shift_active_homeworks(db_session)
        await state.clear()
        await callback.message.edit_text(
            f"✅ **Постоянное расписание на {day_name} сохранено ({len(saved)} уроков)!**\n\n"
            + "\n".join(lines),
            reply_markup=get_admin_panel_keyboard(),
            parse_mode="Markdown"
        )
    else:
        target_d = date.fromisoformat(data["edit_target_date"])
        day_name = DAYS_RU.get(target_d.isoweekday(), "")
        saved = await save_bulk_date_schedule(db_session, target_d, final_lessons)
        await auto_shift_active_homeworks(db_session)

        await state.update_data(
            alert_title=f"📅 **{day_name} ({target_d.strftime('%d.%m.%Y')}):**",
            alert_lines=lines
        )
        await state.set_state(EditDateScheduleStates.confirm_notification)
        preview = (
            f"✅ **Расписание на {day_name} ({target_d.strftime('%d.%m.%Y')}) сохранено ({len(saved)} ур.)!**\n\n"
            + "\n".join(lines) + "\n\n"
            "📢 **Разослать оповещение классу об изменении расписания?**"
        )
        await callback.message.edit_text(preview, reply_markup=get_date_schedule_notify_keyboard(), parse_mode="Markdown")


