import re
from datetime import date
from typing import List, Tuple
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import BellSchedule
from backend.db.crud import set_bell_schedule_item, save_bulk_date_bells
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard, get_date_bells_notify_keyboard
from backend.bot.handlers.schedule import DAYS_RU
from backend.bot.handlers.admin.states import EditDateBellStates, BellWizardStates

router = Router(name="admin_bells_wiz_breaks_router")


def _init_default_breaks(count: int) -> List[int]:
    if count <= 1:
        return []
    breaks = [10] * (count - 1)
    if count >= 3:
        breaks[1] = 15
    if count >= 4:
        breaks[2] = 15
    if count >= 7:
        breaks[-1] = 5
    return breaks


async def init_breaks_step(state: FSMContext, send_func):
    data = await state.get_data()
    count = data.get("bell_count", 7)
    if count <= 1:
        await _show_confirm_screen(state, send_func, custom_breaks=[])
        return

    breaks = _init_default_breaks(count)
    await state.update_data(bell_breaks=breaks)
    await state.set_state(BellWizardStates.configuring_breaks)
    await _render_breaks_overview(state, send_func)


async def _render_breaks_overview(state: FSMContext, send_func):
    data = await state.get_data()
    count = data.get("bell_count", 7)
    breaks: List[int] = data.get("bell_breaks", [])

    lines = [f"• Перемена {i} (после {i} урока): **{b} мин**" for i, b in enumerate(breaks, 1)]
    text = (
        f"🎛 **Шаг 4: Настройка каждой перемены** (уроков: {count})\n\n"
        + "\n".join(lines) + "\n\n"
        "💡 **Как настроить:**\n"
        "1. Нажмите кнопку перемены, чтобы изменить её отдельно.\n"
        "2. Или отправьте длительности сообщением (например: `10 15 15 10`).\n"
        "3. Или выберите быстрый шаблон кнопками ниже:"
    )

    btn_rows = []
    current_row = []
    for i, b in enumerate(breaks, 1):
        current_row.append(InlineKeyboardButton(text=f"✏️ {i}-я: {b}м", callback_data=f"wiz_bedit_{i}"))
        if len(current_row) == 2:
            btn_rows.append(current_row)
            current_row = []
    if current_row:
        btn_rows.append(current_row)

    btn_rows.append([
        InlineKeyboardButton(text="⚡ Все по 10м", callback_data="wiz_bpre_10"),
        InlineKeyboardButton(text="⚡ Все по 15м", callback_data="wiz_bpre_15"),
        InlineKeyboardButton(text="⚡ Все по 5м", callback_data="wiz_bpre_5"),
    ])
    btn_rows.append([InlineKeyboardButton(text="⚡ Стандарт 11 «Б»", callback_data="wiz_bpre_11b")])
    btn_rows.append([
        InlineKeyboardButton(text="➡️ Далее: Сохранение", callback_data="wiz_b_next_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
    ])

    await send_func(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btn_rows), parse_mode="Markdown")


@router.callback_query(F.data.startswith("wiz_bpre_"))
async def cb_bell_break_preset(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.replace("wiz_bpre_", "")
    data = await state.get_data()
    count = data.get("bell_count", 7)
    if count <= 1:
        return

    if mode.isdigit():
        val = int(mode)
        new_breaks = [val] * (count - 1)
    elif mode == "11b":
        new_breaks = _init_default_breaks(count)
    else:
        new_breaks = [10] * (count - 1)

    await state.update_data(bell_breaks=new_breaks)
    await _render_breaks_overview(state, callback.message.edit_text)
    try:
        await callback.answer("Шаблон применен")
    except Exception:
        pass


@router.callback_query(F.data.startswith("wiz_bedit_"))
async def cb_bell_edit_break_single(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("wiz_bedit_", ""))
    data = await state.get_data()
    breaks = data.get("bell_breaks", [])
    cur_val = breaks[idx - 1] if 0 <= idx - 1 < len(breaks) else 10

    await state.update_data(editing_break_idx=idx)
    await state.set_state(BellWizardStates.editing_single_break)

    dur_options = [0, 5, 10, 15, 20, 25, 30]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{d} мин", callback_data=f"wiz_bset_{d}") for d in dur_options[:4]],
            [InlineKeyboardButton(text=f"{d} мин", callback_data=f"wiz_bset_{d}") for d in dur_options[4:]],
            [InlineKeyboardButton(text="🔙 К списку перемен", callback_data="wiz_b_back_to_breaks")]
        ]
    )
    await callback.message.edit_text(
        f"⏱ **Перемена после {idx} урока ({idx} ➔ {idx + 1}):**\n\n"
        f"Текущая длина: **{cur_val} минут**.\n\n"
        "Выберите длительность кнопкой или напишите число минут сообщением (от 0 до 60):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("wiz_bset_"))
async def cb_bell_set_single_break(callback: CallbackQuery, state: FSMContext):
    val = int(callback.data.replace("wiz_bset_", ""))
    await _save_single_break(val, state, callback.message.edit_text)
    try:
        await callback.answer(f"Перемена: {val} мин")
    except Exception:
        pass


@router.message(BellWizardStates.editing_single_break)
async def msg_bell_single_break(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    if not txt.isdigit() or not (0 <= int(txt) <= 120):
        await message.answer("⚠️ Введите число минут от 0 до 120 (например, `15`):")
        return
    await _save_single_break(int(txt), state, message.answer)


async def _save_single_break(val: int, state: FSMContext, send_func):
    data = await state.get_data()
    idx = data.get("editing_break_idx", 1)
    breaks: List[int] = list(data.get("bell_breaks", []))
    if 0 <= idx - 1 < len(breaks):
        breaks[idx - 1] = val
    await state.update_data(bell_breaks=breaks)
    await state.set_state(BellWizardStates.configuring_breaks)
    await _render_breaks_overview(state, send_func)


@router.callback_query(F.data == "wiz_b_back_to_breaks")
async def cb_bell_back_to_breaks(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BellWizardStates.configuring_breaks)
    await _render_breaks_overview(state, callback.message.edit_text)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(BellWizardStates.configuring_breaks)
async def msg_bell_bulk_breaks(message: Message, state: FSMContext):
    txt = message.text or ""
    nums = [int(x) for x in re.findall(r"\b\d+\b", txt)]
    data = await state.get_data()
    count = data.get("bell_count", 7)
    needed = count - 1

    if len(nums) != needed:
        example = " ".join(["10"] * needed)
        await message.answer(
            f"⚠️ Ожидается {needed} чисел (по количеству перемен в расписании). Вы ввели: {len(nums)}.\n"
            f"Пример: `{example}`"
        )
        return

    await state.update_data(bell_breaks=nums)
    await _render_breaks_overview(state, message.answer)


# ==================== STEP 5: CONFIRM & SAVE ====================

def _generate_bells_list(count: int, start_str: str, lesson_dur: int, breaks: List[int]) -> List[Tuple[int, str, str, int]]:
    cur_h, cur_m = map(int, start_str.split(":"))
    current_minutes = cur_h * 60 + cur_m
    bells = []

    for l_num in range(1, count + 1):
        s_h, s_m = divmod(current_minutes, 60)
        end_minutes = current_minutes + lesson_dur
        e_h, e_m = divmod(end_minutes, 60)

        brk = breaks[l_num - 1] if l_num <= len(breaks) else 0

        start_time_str = f"{s_h:02d}:{s_m:02d}"
        end_time_str = f"{e_h:02d}:{e_m:02d}"
        bells.append((l_num, start_time_str, end_time_str, brk))
        current_minutes = end_minutes + brk

    return bells


async def _show_confirm_screen(state: FSMContext, send_func, custom_breaks: List[int] | None = None):
    data = await state.get_data()
    count = data.get("bell_count", 7)
    start_str = data.get("bell_start", "08:30")
    lesson_dur = data.get("bell_duration", 40)
    breaks = custom_breaks if custom_breaks is not None else data.get("bell_breaks", [])

    generated_bells = _generate_bells_list(count, start_str, lesson_dur, breaks)
    await state.update_data(generated_bells=generated_bells)
    await state.set_state(BellWizardStates.confirm_save)

    lines = []
    for num, s, e, b in generated_bells:
        brk_str = f" *(перемена {b} мин)*" if b > 0 else ""
        lines.append(f"• **{num} урок:** `{s}—{e}`{brk_str}")

    target_mode = data.get("bell_target_mode", "perm")
    if target_mode == "perm":
        title = "🗓 **Стандартное расписание звонков (на весь год)**"
    else:
        t_date_str = data.get("bell_target_date") or date.today().isoformat()
        t_date = date.fromisoformat(t_date_str)
        title = f"📅 **Расписание звонков на {DAYS_RU.get(t_date.isoweekday(), '')} ({t_date.strftime('%d.%m.%Y')})**"

    kb_rows = [
        [InlineKeyboardButton(text="✅ Применить и сохранить звонки", callback_data="wiz_b_save")]
    ]
    if count > 1:
        kb_rows.append([InlineKeyboardButton(text="🔙 Изменить перемены", callback_data="wiz_b_back_to_breaks")])
    kb_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])

    await send_func(
        f"{title}\n\n"
        "🔔 **Сформированное расписание:**\n\n"
        + "\n".join(lines) + "\n\n"
        "Сохранить это расписание звонков?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "wiz_b_next_confirm")
async def cb_bell_breaks_done(callback: CallbackQuery, state: FSMContext):
    await _show_confirm_screen(state, callback.message.edit_text)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "wiz_b_save")
async def cb_bell_wizard_save(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    bells = data.get("generated_bells", [])
    target_mode = data.get("bell_target_mode", "perm")

    if target_mode == "perm":
        count = len(bells)
        for l_num, s_t, e_t, brk in bells:
            await set_bell_schedule_item(
                session=db_session,
                lesson_number=l_num,
                start_time=s_t,
                end_time=e_t,
                break_duration=brk,
                specific_date=None
            )
        # Delete obsolete lessons beyond count
        await db_session.execute(
            delete(BellSchedule).where(
                BellSchedule.specific_date.is_(None),
                BellSchedule.lesson_number > count
            )
        )
        await db_session.commit()
        await state.clear()
        await callback.message.edit_text(
            f"✅ **Стандартное расписание звонков успешно сохранено ({count} уроков)!**",
            reply_markup=get_admin_panel_keyboard(),
            parse_mode="Markdown"
        )
    else:
        target_d = date.fromisoformat(data["bell_target_date"])
        await save_bulk_date_bells(db_session, target_d, bells)

        day_name = DAYS_RU.get(target_d.isoweekday(), "День")
        bell_lines = [f"{n} урок: {s} – {e}" for n, s, e, _ in bells]
        await state.update_data(
            alert_title=f"🔔 **Новые звонки на {day_name} ({target_d.strftime('%d.%m.%Y')}):**\n" + "\n".join(bell_lines),
            alert_lines=bell_lines
        )
        await state.set_state(EditDateBellStates.confirm_notification)

        await callback.message.edit_text(
            f"✅ **Расписание звонков на {day_name} ({target_d.strftime('%d.%m.%Y')}) сохранено!**\n\n"
            "📢 **Разослать классу и в беседы уведомление об изменении звонков?**",
            reply_markup=get_date_bells_notify_keyboard(),
            parse_mode="Markdown"
        )
    try:
        await callback.answer("Звонки сохранены!")
    except Exception:
        pass
