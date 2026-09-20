import re
from datetime import date
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import (
    get_bell_schedule, get_bell_schedule_for_date, set_bell_schedule_item,
    set_bell_break_duration, clear_date_bells, save_bulk_date_bells
)
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_date_bells_notify_keyboard
)
from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.services.notifier import send_schedule_change_alert
from backend.bot.handlers.schedule import DAYS_RU
from backend.bot.handlers.admin.helpers import is_admin, parse_bells_text
from backend.bot.handlers.admin.states import EditBellStates, EditDateBellStates, EditBreakStates, BellWizardStates

router = Router(name='admin_bells_std_router')

# ==================== MAIN BELLS MENU ====================

@router.callback_query(F.data == "admin_edit_bells")
async def cb_bells_menu(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    bells = await get_bell_schedule(db_session)
    bell_text = "\n".join([
        f"• **{b.lesson_number} урок:** `{b.start_time}—{b.end_time}` (перемена {b.break_duration} мин)"
        for b in bells
    ]) if bells else "Расписание звонков не заполнено"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎛 Пошаговый конструктор звонков (кнопками)", callback_data="adm_bell_wizard")
            ],
            [
                InlineKeyboardButton(text="⚡ Изменить перемены", callback_data="adm_quick_breaks"),
                InlineKeyboardButton(text="⏰ Изменить время уроков", callback_data="adm_edit_bell_times")
            ],
            [
                InlineKeyboardButton(text="📅 Звонки на дату (сокращенные)", callback_data="adm_date_bells")
            ],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")]
        ]
    )

    await callback.message.edit_text(
        f"🔔 **Текущее расписание звонков:**\n\n"
        f"{bell_text}\n\n"
        "Выберите, что хотите настроить:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


# ==================== QUICK BREAKS ====================

@router.callback_query(F.data == "adm_quick_breaks")
async def cb_quick_breaks_lesson_pick(callback: CallbackQuery, state: FSMContext):
    btns = [
        [InlineKeyboardButton(text=f"После {i} урока", callback_data=f"adm_brk_l_{i}") for i in range(1, 5)],
        [InlineKeyboardButton(text=f"После {i} урока", callback_data=f"adm_brk_l_{i}") for i in range(5, 9)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_edit_bells")]
    ]
    await state.set_state(EditBreakStates.choosing_lesson)
    await callback.message.edit_text(
        "⚡ **Быстрая настройка перемен:**\n\nПосле какого урока изменить длительность перемены?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_brk_l_"))
async def cb_quick_breaks_duration_pick(callback: CallbackQuery, state: FSMContext):
    l_num = int(callback.data.replace("adm_brk_l_", ""))
    await state.update_data(break_lesson=l_num)

    durations = [5, 10, 15, 20, 25, 30]
    btns = [
        [InlineKeyboardButton(text=f"{d} мин", callback_data=f"adm_brk_d_{d}") for d in durations[:3]],
        [InlineKeyboardButton(text=f"{d} мин", callback_data=f"adm_brk_d_{d}") for d in durations[3:]],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="adm_quick_breaks")]
    ]

    await state.set_state(EditBreakStates.choosing_duration)
    await callback.message.edit_text(
        f"⏳ **Выберите длительность перемены после {l_num}-го урока:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_brk_d_"))
async def cb_save_quick_break(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    duration = int(callback.data.replace("adm_brk_d_", ""))
    data = await state.get_data()
    l_num = data.get("break_lesson", 1)

    await set_bell_break_duration(db_session, lesson_number=l_num, break_duration=duration)
    await state.clear()

    bells = await get_bell_schedule(db_session)
    bell_lines = [
        f"• **{b.lesson_number} урок:** `{b.start_time}—{b.end_time}` (перемена {b.break_duration} мин)"
        for b in bells
    ] if bells else []

    await callback.message.edit_text(
        f"✅ Перемена после {l_num}-го урока установлена на **{duration} минут**!\n\n"
        f"⏰ **Расписание звонков автоматически пересчитано:**\n"
        + "\n".join(bell_lines),
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Пересчитано и сохранено!")
    except Exception:
        pass


# ==================== INDIVIDUAL BELL TIMES ====================

@router.callback_query(F.data == "adm_edit_bell_times")
async def cb_start_edit_bells(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    btns = [
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_b_l_{i}") for i in range(1, 5)],
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_b_l_{i}") for i in range(5, 9)],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")]
    ]

    await state.set_state(EditBellStates.choosing_lesson)
    await callback.message.edit_text(
        "🔔 **Редактор времени звонков:**\n\nВыберите номер урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_b_l_"))
async def cb_edit_bell_chosen(callback: CallbackQuery, state: FSMContext):
    l_num = int(callback.data.replace("adm_b_l_", ""))
    await state.update_data(bell_lesson=l_num)

    await state.set_state(EditBellStates.entering_times)
    await callback.message.edit_text(
        f"🔔 **Настройка времени для {l_num}-го урока:**\n\n"
        "Введите время начала, конца и перемены через пробел или дефис.\n"
        "**Пример:** `08:30-09:15 15` *(где 15 — перемена в минутах)*",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(EditBellStates.entering_times)
async def msg_edit_bell_save(message: Message, state: FSMContext, db_session: AsyncSession):
    text = message.text.strip()
    match = re.match(r"(\d{1,2}:\d{2})\s*[-—–]\s*(\d{1,2}:\d{2})(?:\s+(\d+))?", text)
    if not match:
        await message.answer("⚠️ Неверный формат. Введите время как: `08:30-09:15 15`:")
        return

    start_t, end_t, brk = match.groups()
    break_duration = int(brk) if brk else 10

    data = await state.get_data()
    l_num = data["bell_lesson"]

    await set_bell_schedule_item(
        session=db_session,
        lesson_number=l_num,
        start_time=start_t,
        end_time=end_t,
        break_duration=break_duration
    )

    await state.clear()
    await message.answer(
        f"✅ **Звонки для {l_num}-го урока обновлены!**\n\n"
        f"⏰ `{start_t} — {end_t}` (перемена {break_duration} мин)",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )


