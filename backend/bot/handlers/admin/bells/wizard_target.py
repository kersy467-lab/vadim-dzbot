from datetime import date
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.handlers.admin.states import BellWizardStates

router = Router(name="admin_bells_wiz_target_router")


@router.callback_query(F.data == "adm_bell_wizard")
async def cb_bell_wizard_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BellWizardStates.choosing_target)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗓 Стандартные звонки (на весь год)", callback_data="wiz_b_tgt_perm")],
            [InlineKeyboardButton(text="📅 Звонки на дату (сокращенные/особые)", callback_data="wiz_b_tgt_date")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_edit_bells")]
        ]
    )
    await callback.message.edit_text(
        "🎛 **Пошаговый конструктор звонков (кнопками)**\n\n"
        "Для чего вы хотите настроить звонки?",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_dtb_wizard")
async def cb_bell_wizard_start_from_date(callback: CallbackQuery, state: FSMContext):
    from backend.bot.handlers.admin.bells.wizard_params import show_bell_wizard_count
    data = await state.get_data()
    target_d_str = data.get("edit_bell_target_date")
    await state.update_data(bell_target_mode="date", bell_target_date=target_d_str)
    await state.set_state(BellWizardStates.choosing_count)
    await show_bell_wizard_count(callback)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "wiz_b_tgt_perm")
async def cb_bell_target_perm(callback: CallbackQuery, state: FSMContext):
    from backend.bot.handlers.admin.bells.wizard_params import show_bell_wizard_count
    await state.update_data(bell_target_mode="perm")
    await state.set_state(BellWizardStates.choosing_count)
    await show_bell_wizard_count(callback)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "wiz_b_tgt_date")
async def cb_bell_target_date_pick(callback: CallbackQuery, state: FSMContext):
    from backend.config import get_today
    today = get_today()
    kb = get_inline_calendar("wiz_bd", year=today.year, month=today.month, back_callback="adm_bell_wizard")
    await state.set_state(BellWizardStates.choosing_date)
    await callback.message.edit_text(
        "📅 **Выберите дату для настройки расписания звонков:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_nav_wiz_bd_"))
async def cb_cal_nav_wiz_bd(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    kb = get_inline_calendar("wiz_bd", year=year, month=month, back_callback="adm_bell_wizard")
    await callback.message.edit_text(
        "📅 **Выберите дату для настройки расписания звонков:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_act_wiz_bd_"))
async def cb_cal_act_wiz_bd(callback: CallbackQuery, state: FSMContext):
    from backend.bot.handlers.admin.bells.wizard_params import show_bell_wizard_count
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    day = int(parts[6])
    target_d = date(year, month, day)

    await state.update_data(
        bell_target_mode="date",
        bell_target_date=target_d.isoformat(),
        edit_bell_target_date=target_d.isoformat()
    )
    await state.set_state(BellWizardStates.choosing_count)
    await show_bell_wizard_count(callback)
    try:
        await callback.answer()
    except Exception:
        pass
