from datetime import date, datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import get_all_subjects, get_subject_by_id
from backend.bot.keyboards.admin_kb import get_cancel_keyboard
from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.handlers.schedule import DAYS_RU
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.states import AddHomeworkStates
from backend.bot.handlers.admin.homework.helpers import (
    escape_md, safe_answer, safe_edit_text,
    find_subject_by_text, build_subjects_keyboard_grid, get_upcoming_or_fallback_dates,
    build_date_keyboard, proceed_to_entering_content, is_saturday_physics
)

router = Router(name="admin_homework_add_picker_router")


@router.callback_query(F.data == "admin_add_hw")
async def cb_start_add_hw(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    subjects = await get_all_subjects(db_session)
    kb = build_subjects_keyboard_grid(subjects)

    await state.set_state(AddHomeworkStates.choosing_subject)
    await safe_edit_text(
        callback.message,
        "📚 **Добавление ДЗ:**\n"
        "Выберите предмет кнопкой ниже или просто напишите его название в чат (например, *Русский*, *Алгебра*, *Физика*):",
        reply_markup=kb
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_hw_s_"))
async def cb_add_hw_subject_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    subj_id = int(callback.data.replace("adm_hw_s_", ""))
    await proceed_to_entering_content(callback, state, db_session, subj_id)


@router.message(AddHomeworkStates.choosing_subject)
async def msg_add_hw_subject_text(message: Message, state: FSMContext, db_session: AsyncSession):
    text = (message.text or "").strip()
    if not text:
        return

    subjects = await get_all_subjects(db_session)
    subj = find_subject_by_text(text, subjects)
    if subj:
        await proceed_to_entering_content(message, state, db_session, subj.id)
        return

    kb = build_subjects_keyboard_grid(subjects)
    await safe_answer(
        message,
        f"⚠️ Предмет *«{escape_md(text)}»* не найден в списке.\n\n"
        "Пожалуйста, выберите предмет кнопкой ниже или напишите одно из названий (например, *Русский*, *Алгебра*, *Литература*):",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("adm_hw_d_"))
async def cb_add_hw_date_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    target_d_str = callback.data.replace("adm_hw_d_", "")
    target_d = date.fromisoformat(target_d_str)

    data = await state.get_data()
    subj_id = data.get("subject_id", 0)
    subj = await get_subject_by_id(db_session, subj_id)
    subj_name = subj.name if subj else "Предмет"

    if is_saturday_physics(subj_name, target_d):
        await callback.answer("⚠️ Субботняя физика — отдельное занятие, на неё нельзя назначить ДЗ!", show_alert=True)
        return

    await state.update_data(due_date=target_d.isoformat())

    from backend.config import get_today
    today = get_today()
    dates, is_sched = await get_upcoming_or_fallback_dates(
        db_session, subj_id, from_date=today + timedelta(days=1), limit=4
    )

    if target_d not in dates:
        dates = [target_d] + [d for d in dates if d != target_d][:3]
        dates.sort()

    kb = build_date_keyboard(dates, selected_date=target_d, is_scheduled=is_sched)
    d_name = DAYS_RU.get(target_d.isoweekday(), "")
    text = (
        f"📚 **Добавление ДЗ — {subj_name}**\n\n"
        f"📅 **Выбранная дата сдачи:**\n"
        f"👉 **{d_name}, {target_d.strftime('%d.%m.%Y')}**\n\n"
        "✍️ **Отправьте задание в чат:**\n"
        "• Текстом (номера упражнений, параграфы)\n"
        "• Либо сразу фото или документ с подписью!"
    )

    await safe_edit_text(callback.message, text, reply_markup=kb)
    try:
        await callback.answer(f"Выбрана дата: {target_d.strftime('%d.%m.%Y')}")
    except Exception:
        pass


@router.callback_query(F.data == "adm_hw_open_cal")
async def cb_add_hw_open_cal(callback: CallbackQuery, state: FSMContext):
    from backend.config import get_today
    today = get_today()
    kb = get_inline_calendar("adm_hw", year=today.year, month=today.month, back_callback="admin_cancel")
    await state.set_state(AddHomeworkStates.entering_date)
    await safe_edit_text(
        callback.message,
        "📅 **Выберите дату на календаре для сдачи ДЗ:**",
        reply_markup=kb
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_nav_adm_hw_"))
async def cb_cal_nav_adm_hw(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    kb = get_inline_calendar("adm_hw", year=year, month=month, back_callback="admin_cancel")
    await safe_edit_text(
        callback.message,
        "📅 **Выберите дату на календаре для сдачи ДЗ:**",
        reply_markup=kb
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_act_adm_hw_"))
async def cb_cal_act_adm_hw(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    day = int(parts[6])
    due_d = date(year, month, day)

    data = await state.get_data()
    subj = await get_subject_by_id(db_session, data.get("subject_id", 0))
    subj_name = subj.name if subj else "Предмет"

    if is_saturday_physics(subj_name, due_d):
        await callback.answer(
            "⚠️ Субботняя физика — отдельное занятие, на неё нельзя назначить ДЗ. Выберите другой день!",
            show_alert=True
        )
        return

    await state.update_data(due_date=due_d.isoformat())
    await state.set_state(AddHomeworkStates.entering_content)
    day_ru = DAYS_RU.get(due_d.isoweekday(), "")

    await safe_edit_text(
        callback.message,
        f"📚 **Добавление ДЗ — {subj_name}**\n\n"
        f"📅 **Выбранная дата сдачи:**\n"
        f"👉 **{day_ru}, {due_d.strftime('%d.%m.%Y')}**\n\n"
        "✍️ **Отправьте задание в чат одним сообщением:**\n"
        "• Текстом (номера, параграфы)\n"
        "• Либо фото, документом (PDF, Word) или файлом с подписью!",
        reply_markup=get_cancel_keyboard()
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(AddHomeworkStates.entering_date)
async def msg_add_hw_date_text(message: Message, state: FSMContext, db_session: AsyncSession):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        data = await state.get_data()
        subj = await get_subject_by_id(db_session, data.get("subject_id", 0))
        subj_name = subj.name if subj else "Предмет"

        if is_saturday_physics(subj_name, dt):
            await safe_answer(
                message,
                "⚠️ **Субботняя физика — отдельное занятие.**\n"
                "Домашнее задание по физике на этот день не назначается.\n"
                "Пожалуйста, выберите рабочий учебный день (например, вторник или четверг):"
            )
            return

        await state.update_data(due_date=dt.isoformat())
        await state.set_state(AddHomeworkStates.entering_content)
        day_ru = DAYS_RU.get(dt.isoweekday(), "")
        await safe_answer(
            message,
            f"📚 **Добавление ДЗ — {subj_name}**\n\n"
            f"📅 **Выбранная дата сдачи:**\n"
            f"👉 **{day_ru}, {dt.strftime('%d.%m.%Y')}**\n\n"
            "✍️ **Отправьте задание в чат одним сообщением:**\n"
            "• Текстом (номера, параграфы)\n"
            "• Либо фото, документом (PDF, Word) или файлом с подписью!",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await safe_answer(message, "⚠️ Неверный формат даты. Выберите день на календаре или введите дату как `ДД.ММ.ГГГГ`:")
