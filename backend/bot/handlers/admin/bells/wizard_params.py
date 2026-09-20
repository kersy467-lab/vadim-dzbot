import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from backend.bot.handlers.admin.states import BellWizardStates

router = Router(name="admin_bells_wiz_params_router")


# ==================== STEP 1: LESSON COUNT (1-8) ====================

async def show_bell_wizard_count(target):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{i} ур.", callback_data=f"wiz_bc_{i}") for i in range(1, 5)],
            [InlineKeyboardButton(text=f"{i} ур.", callback_data=f"wiz_bc_{i}") for i in range(5, 9)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )
    text = (
        "🎛 **Шаг 1: Количество уроков**\n\n"
        "Сколько уроков будет в расписании (от 1 до 8)?\n"
        "Выберите кнопку или введите число сообщением:"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("wiz_bc_"))
async def cb_bell_count_chosen(callback: CallbackQuery, state: FSMContext):
    cnt = int(callback.data.replace("wiz_bc_", ""))
    await _proceed_to_start_time(cnt, state, callback.message.edit_text)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(BellWizardStates.choosing_count)
async def msg_bell_count(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    if not txt.isdigit() or not (1 <= int(txt) <= 8):
        await message.answer("⚠️ Введите число уроков от 1 до 8 (или выберите кнопку выше):")
        return
    cnt = int(txt)
    await _proceed_to_start_time(cnt, state, message.answer)


async def _proceed_to_start_time(cnt: int, state: FSMContext, send_func):
    await state.update_data(bell_count=cnt)
    await state.set_state(BellWizardStates.choosing_start)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="08:00", callback_data="wiz_bs_08:00"),
             InlineKeyboardButton(text="08:15", callback_data="wiz_bs_08:15"),
             InlineKeyboardButton(text="08:30 (стандарт)", callback_data="wiz_bs_08:30")],
            [InlineKeyboardButton(text="08:45", callback_data="wiz_bs_08:45"),
             InlineKeyboardButton(text="09:00", callback_data="wiz_bs_09:00"),
             InlineKeyboardButton(text="09:15", callback_data="wiz_bs_09:15")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )
    await send_func(
        f"🎛 **Шаг 2: Время начала 1-го урока** (уроков: {cnt})\n\n"
        "Во сколько начинается первый урок?\n"
        "Выберите вариант или напишите своё время сообщением (например, `08:40`):",
        reply_markup=kb,
        parse_mode="Markdown"
    )


# ==================== STEP 2: START TIME ====================

@router.callback_query(F.data.startswith("wiz_bs_"))
async def cb_bell_start_chosen(callback: CallbackQuery, state: FSMContext):
    start_time = callback.data.replace("wiz_bs_", "")
    await _proceed_to_duration(start_time, state, callback.message.edit_text)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(BellWizardStates.choosing_start)
async def msg_bell_start(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    match = re.match(r"^(0?[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$", txt)
    if not match:
        await message.answer("⚠️ Введите корректное время в формате `ЧЧ:ММ` (например, `08:40` или `09:00`):")
        return
    h, m = int(match.group(1)), int(match.group(2))
    norm_time = f"{h:02d}:{m:02d}"
    await _proceed_to_duration(norm_time, state, message.answer)


async def _proceed_to_duration(start_time: str, state: FSMContext, send_func):
    await state.update_data(bell_start=start_time)
    await state.set_state(BellWizardStates.choosing_duration)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="45 мин (Полный)", callback_data="wiz_bdur_45"),
             InlineKeyboardButton(text="40 мин (Стандарт)", callback_data="wiz_bdur_40")],
            [InlineKeyboardButton(text="35 мин (Сокращ.)", callback_data="wiz_bdur_35"),
             InlineKeyboardButton(text="30 мин (Сокращ.)", callback_data="wiz_bdur_30"),
             InlineKeyboardButton(text="20 мин", callback_data="wiz_bdur_20")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )
    await send_func(
        f"🎛 **Шаг 3: Длительность одного урока** (начало в {start_time})\n\n"
        "Сколько минут длится каждый урок?\n"
        "Выберите кнопку или напишите число минут сообщением (например, `40`):",
        reply_markup=kb,
        parse_mode="Markdown"
    )


# ==================== STEP 3: DURATION ====================

@router.callback_query(F.data.startswith("wiz_bdur_"))
async def cb_bell_duration_chosen(callback: CallbackQuery, state: FSMContext):
    dur = int(callback.data.replace("wiz_bdur_", ""))
    await _proceed_from_duration(dur, state, callback.message.edit_text)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(BellWizardStates.choosing_duration)
async def msg_bell_duration(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    if not txt.isdigit() or not (10 <= int(txt) <= 180):
        await message.answer("⚠️ Введите длительность урока от 10 до 180 минут (например, `40`):")
        return
    dur = int(txt)
    await _proceed_from_duration(dur, state, message.answer)


async def _proceed_from_duration(dur: int, state: FSMContext, send_func):
    from backend.bot.handlers.admin.bells.wizard_breaks import init_breaks_step
    await state.update_data(bell_duration=dur)
    await init_breaks_step(state, send_func)
