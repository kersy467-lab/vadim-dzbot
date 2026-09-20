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

router = Router(name='admin_bells_date_router')

# ==================== DATE-SPECIFIC BELLS ====================

@router.callback_query(F.data == "adm_date_bells")
async def cb_admin_date_bells(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from backend.config import get_today
    today = get_today()
    kb = get_inline_calendar("adm_dtb", year=today.year, month=today.month, back_callback="admin_edit_bells")
    await callback.message.edit_text(
        "📅 **Расписание звонков на определенный день**\n\n"
        "Выберите дату в календаре, для которой нужно настроить особое расписание звонков (например, сокращенные уроки):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_nav_adm_dtb_"))
async def cb_cal_nav_adm_dtb(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    kb = get_inline_calendar("adm_dtb", year=year, month=month, back_callback="admin_edit_bells")
    await callback.message.edit_text(
        "📅 **Расписание звонков на определенный день**\n\n"
        "Выберите дату в календаре:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_act_adm_dtb_"))
async def cb_cal_act_adm_dtb(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    day = int(parts[6])
    target_d = date(year, month, day)

    await state.update_data(edit_bell_target_date=target_d.isoformat())
    await state.set_state(EditDateBellStates.choosing_date)

    day_name = DAYS_RU.get(target_d.isoweekday(), "День")
    bells = await get_bell_schedule_for_date(db_session, target_d)

    bell_lines = []
    for b in bells:
        brk = f" *(перемена {b.break_duration} мин)*" if b.break_duration else ""
        bell_lines.append(f"• **{b.lesson_number} урок:** `{b.start_time}—{b.end_time}`{brk}")

    text = (
        f"📅 **Звонки на {day_name} ({target_d.strftime('%d.%m.%Y')}):**\n\n"
        + "\n".join(bell_lines) + "\n\n"
        "Выберите готовый шаблон или введите свое расписание звонков:"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎛 Пошаговый конструктор (кнопками)", callback_data="adm_dtb_wizard")],
            [InlineKeyboardButton(text="⚡ Сокращенные уроки (по 35 мин)", callback_data="adm_dtb_p35")],
            [InlineKeyboardButton(text="⚡ Сокращенные уроки (по 30 мин)", callback_data="adm_dtb_p30")],
            [InlineKeyboardButton(text="✏️ Ввести звонки текстом (свободно)", callback_data="adm_dtb_bulk")],
            [InlineKeyboardButton(text="🗑 Сбросить (к стандартным)", callback_data="adm_dtb_reset")],
            [InlineKeyboardButton(text="🔙 К выбору даты", callback_data="adm_date_bells")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_dtb_p35")
async def cb_dtb_preset_35(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    target_d_str = data.get("edit_bell_target_date")
    if not target_d_str:
        await callback.answer("Выберите дату заново", show_alert=True)
        return
    target_d = date.fromisoformat(target_d_str)
    day_name = DAYS_RU.get(target_d.isoweekday(), "День")

    p35 = [
        (1, "08:30", "09:05", 10),
        (2, "09:15", "09:50", 10),
        (3, "10:00", "10:35", 15),
        (4, "10:50", "11:25", 10),
        (5, "11:35", "12:10", 10),
        (6, "12:20", "12:55", 10),
        (7, "13:05", "13:40", 5),
        (8, "13:45", "14:20", 0),
    ]

    await save_bulk_date_bells(db_session, target_d, p35)

    bell_lines = [f"{n} урок: {s} – {e}" for n, s, e, _ in p35]
    await state.update_data(
        alert_title=f"🔔 **Сокращенные звонки (по 35 мин) на {day_name} ({target_d.strftime('%d.%m.%Y')}):**",
        alert_lines=bell_lines
    )
    await state.set_state(EditDateBellStates.confirm_notification)

    await callback.message.edit_text(
        f"✅ **Установлены сокращенные уроки по 35 минут на {target_d.strftime('%d.%m.%Y')}!**\n\n"
        "📢 **Разослать оповещение классу об изменении звонков?**",
        reply_markup=get_date_bells_notify_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сохранено!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_dtb_p30")
async def cb_dtb_preset_30(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    target_d_str = data.get("edit_bell_target_date")
    if not target_d_str:
        await callback.answer("Выберите дату заново", show_alert=True)
        return
    target_d = date.fromisoformat(target_d_str)
    day_name = DAYS_RU.get(target_d.isoweekday(), "День")

    p30 = [
        (1, "08:30", "09:00", 10),
        (2, "09:10", "09:40", 10),
        (3, "09:50", "10:20", 10),
        (4, "10:30", "11:00", 10),
        (5, "11:10", "11:40", 10),
        (6, "11:50", "12:20", 10),
        (7, "12:30", "13:00", 5),
        (8, "13:05", "13:35", 0),
    ]

    await save_bulk_date_bells(db_session, target_d, p30)

    bell_lines = [f"{n} урок: {s} – {e}" for n, s, e, _ in p30]
    await state.update_data(
        alert_title=f"🔔 **Сокращенные звонки (по 30 мин) на {day_name} ({target_d.strftime('%d.%m.%Y')}):**",
        alert_lines=bell_lines
    )
    await state.set_state(EditDateBellStates.confirm_notification)

    await callback.message.edit_text(
        f"✅ **Установлены сокращенные уроки по 30 минут на {target_d.strftime('%d.%m.%Y')}!**\n\n"
        "📢 **Разослать оповещение классу об изменении звонков?**",
        reply_markup=get_date_bells_notify_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сохранено!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_dtb_bulk")
async def cb_dtb_bulk_prompt(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target_d_str = data.get("edit_bell_target_date")
    if not target_d_str:
        await callback.answer("Выберите дату заново", show_alert=True)
        return
    target_d = date.fromisoformat(target_d_str)
    day_name = DAYS_RU.get(target_d.isoweekday(), "День")

    await state.set_state(EditDateBellStates.entering_text_bulk)
    await callback.message.edit_text(
        f"✏️ **Введите расписание звонков на {day_name} ({target_d.strftime('%d.%m.%Y')}):**\n\n"
        "Формат свободный — с номерами уроков или без, построчно или через запятую, например:\n"
        "```text\n"
        "1. 08:30 - 09:05\n"
        "2. 09:15 - 09:50\n"
        "3. 10:00 - 10:35\n"
        "4. 10:45 - 11:20\n"
        "```\n"
        "_(Перемены между уроками рассчитаются автоматически)_",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(EditDateBellStates.entering_text_bulk)
async def msg_dtb_bulk_save(message: Message, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    target_d = date.fromisoformat(data["edit_bell_target_date"])
    day_name = DAYS_RU.get(target_d.isoweekday(), "День")

    parsed = parse_bells_text(message.text)
    if not parsed:
        await message.answer(
            "⚠️ Не удалось распознать время уроков. Пожалуйста, укажите время уроков (например, `08:30 - 09:10`):",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
        return

    await save_bulk_date_bells(db_session, target_d, parsed)

    bell_lines = [f"{l_num} урок: {s} – {e} (перемена {b} мин)" for l_num, s, e, b in parsed]
    await state.update_data(
        alert_title=f"🔔 **Новое расписание звонков на {day_name} ({target_d.strftime('%d.%m.%Y')}):**",
        alert_lines=bell_lines
    )
    await state.set_state(EditDateBellStates.confirm_notification)

    await message.answer(
        f"✅ **Расписание звонков на {target_d.strftime('%d.%m.%Y')} сохранено ({len(parsed)} ур.)!**\n\n"
        + "\n".join(bell_lines) + "\n\n"
        "📢 **Разослать оповещение классу об изменении звонков?**",
        reply_markup=get_date_bells_notify_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "adm_dtb_reset")
async def cb_dtb_reset(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    target_d_str = data.get("edit_bell_target_date")
    if not target_d_str:
        await callback.answer("Выберите дату заново", show_alert=True)
        return
    target_d = date.fromisoformat(target_d_str)
    day_name = DAYS_RU.get(target_d.isoweekday(), "День")

    await clear_date_bells(db_session, target_d)

    perm_bells = await get_bell_schedule(db_session)
    bell_lines = [f"{b.lesson_number} урок: {b.start_time} – {b.end_time}" for b in perm_bells]

    await state.update_data(
        alert_title=f"🔔 **{day_name} ({target_d.strftime('%d.%m.%Y')}):**\n_(Расписание звонков возвращено к стандартному)_",
        alert_lines=bell_lines
    )
    await state.set_state(EditDateBellStates.confirm_notification)

    await callback.message.edit_text(
        f"🗑 **Расписание звонков на {target_d.strftime('%d.%m.%Y')} сброшено к стандартному!**\n\n"
        "📢 **Оповестить класс о возврате к стандартным звонкам?**",
        reply_markup=get_date_bells_notify_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сброшено!")
    except Exception:
        pass


@router.callback_query(F.data.in_(["adm_dtb_notify_groups", "adm_dtb_notify_pm", "adm_dtb_notify_all", "adm_dtb_notify_yes"]))
async def cb_dtb_notify_yes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    title = data.get("alert_title", "Изменение расписания звонков")
    lines = data.get("alert_lines", [])

    to_groups = callback.data in ("adm_dtb_notify_groups", "adm_dtb_notify_all", "adm_dtb_notify_yes")
    to_users = callback.data in ("adm_dtb_notify_pm", "adm_dtb_notify_all", "adm_dtb_notify_yes")

    await send_schedule_change_alert(bot, title, lines, to_groups=to_groups, to_users=to_users)
    await state.clear()
    dest_text = "в чат и в ЛС" if (to_groups and to_users) else ("в чат" if to_groups else "в ЛС")
    await callback.message.edit_text(
        f"📢 **Оповещение об изменении звонков успешно разослано ({dest_text})!**",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Разослано!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_dtb_notify_no")
async def cb_dtb_notify_no(callback: CallbackQuery, state: FSMContext):
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


