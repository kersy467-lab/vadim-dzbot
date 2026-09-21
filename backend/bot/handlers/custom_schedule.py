import re
from typing import Optional, Dict, Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import (
    get_user_custom_schedules,
    save_user_custom_schedules,
    get_user_by_tg_id
)

router = Router(name="custom_schedule_router")

TIME_REGEX = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

DAYS_INFO = [
    (1, "Понедельник", "понедельник"),
    (2, "Вторник", "вторник"),
    (3, "Среда", "среду"),
    (4, "Четверг", "четверг"),
    (5, "Пятница", "пятницу"),
    (6, "Суббота", "субботу"),
    (7, "Воскресенье", "воскресенье"),
]


class CustomScheduleStates(StatesGroup):
    waiting_for_content = State()
    waiting_for_time = State()


def get_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить настройку", callback_data="custom_sched_cancel")]
        ]
    )


def format_day_prompt(day_num: int) -> str:
    name, acc = DAYS_INFO[day_num - 1][1], DAYS_INFO[day_num - 1][2]
    return (
        f"📅 <b>{name}</b>\n\n"
        f"Отправьте расписание на <b>{acc}</b>.\n\n"
        "Можно:\n"
        "• отправить фотографию;\n"
        "• написать расписание текстом;\n"
        "• если на этот день ничего отправлять не нужно — отправьте <code>-</code>."
    )


def format_summary_text(schedules: list) -> str:
    if not schedules:
        return (
            "📋 <b>Ваше персональное расписание ещё не настроено.</b>\n\n"
            "Вы можете настроить автоматическую ежедневную отправку своего расписания в удобное время."
        )

    lines = ["📋 <b>Ваше персональное расписание:</b>\n"]
    sched_map = {s.day_of_week: s for s in schedules}

    for day_num, name, _ in DAYS_INFO:
        sched = sched_map.get(day_num)
        if sched and sched.is_active:
            type_label = "фото" if sched.content_type == "photo" else "текст"
            lines.append(f"• <b>{name}</b> — <code>{sched.notification_time}</code> ✅ <i>({type_label})</i>")
        else:
            lines.append(f"• <b>{name}</b> — отключено ⚪")

    lines.append("\n<i>Бот автоматически пришлёт расписание в указанное время.</i>")
    return "\n".join(lines)


@router.callback_query(F.data == "custom_sched_add")
async def start_custom_schedule_wizard(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(CustomScheduleStates.waiting_for_content)
    await state.update_data(current_day=1, schedule_data={})

    await callback.message.answer(
        "🚀 <b>Настройка персонального расписания</b>\n\n"
        "Вы пройдете пошаговую настройку на каждый день недели (с понедельника по воскресенье).\n\n"
        + format_day_prompt(1),
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "custom_sched_cancel")
async def cancel_custom_schedule(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "❌ Настройка персонального расписания отменена.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="open_settings")]
            ]
        )
    )
    try:
        await callback.answer("Отменено")
    except Exception:
        pass


@router.callback_query(F.data == "custom_sched_view")
async def view_custom_schedule(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    schedules = await get_user_custom_schedules(db_session, current_user.tg_id)
    text = format_summary_text(schedules)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить расписание" if schedules else "📅 Добавить своё расписание",
                    callback_data="custom_sched_add"
                )
            ],
            [
                InlineKeyboardButton(text="🔙 К настройкам", callback_data="open_settings")
            ]
        ]
    )

    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(CustomScheduleStates.waiting_for_content)
async def handle_schedule_content(message: Message, state: FSMContext, db_session: AsyncSession, current_user: User):
    data = await state.get_data()
    day = data.get("current_day", 1)
    sched_data = data.get("schedule_data", {})

    text_input = (message.text or "").strip()

    # Проверка на пропуск дня
    if text_input in ("-", "—", "--", "- "):
        sched_data[day] = {"is_active": False}
        if day < 7:
            next_day = day + 1
            await state.update_data(current_day=next_day, schedule_data=sched_data)
            await message.answer(
                f"День {DAYS_INFO[day - 1][1]} отключён ⚪\n\n" + format_day_prompt(next_day),
                reply_markup=get_cancel_kb(),
                parse_mode="HTML"
            )
        else:
            await finish_custom_schedule(message, state, db_session, current_user, sched_data)
        return

    # Фото
    if message.photo:
        file_id = message.photo[-1].file_id
        await state.update_data(pending_content={"content_type": "photo", "file_id": file_id})
        await state.set_state(CustomScheduleStates.waiting_for_time)
        await message.answer(
            f"Фото для <b>{DAYS_INFO[day - 1][1]}</b> принято 📷\n\n"
            "⏰ <b>Во сколько отправлять вам это расписание?</b>\n"
            "Пример: <code>15:30</code>",
            reply_markup=get_cancel_kb(),
            parse_mode="HTML"
        )
        return

    # Текст
    if message.text:
        await state.update_data(pending_content={"content_type": "text", "text_content": message.text})
        await state.set_state(CustomScheduleStates.waiting_for_time)
        await message.answer(
            f"Текст для <b>{DAYS_INFO[day - 1][1]}</b> принят 📝\n\n"
            "⏰ <b>Во сколько отправлять вам это расписание?</b>\n"
            "Пример: <code>15:30</code>",
            reply_markup=get_cancel_kb(),
            parse_mode="HTML"
        )
        return

    # Неподдерживаемый тип контента
    await message.answer(
        "⚠️ Пожалуйста, отправьте фотографию, текст расписания или знак <code>-</code>, если этот день не нужен.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )


@router.message(CustomScheduleStates.waiting_for_time)
async def handle_schedule_time(message: Message, state: FSMContext, db_session: AsyncSession, current_user: User):
    time_str = (message.text or "").strip()

    if not TIME_REGEX.match(time_str):
        await message.answer(
            "⚠️ <b>Некорректное время.</b>\n"
            "Введите время в формате <code>HH:MM</code>, например: <code>15:30</code>.",
            reply_markup=get_cancel_kb(),
            parse_mode="HTML"
        )
        return

    data = await state.get_data()
    day = data.get("current_day", 1)
    sched_data = data.get("schedule_data", {})
    pending = data.get("pending_content", {})

    sched_data[day] = {
        "is_active": True,
        "content_type": pending.get("content_type"),
        "file_id": pending.get("file_id"),
        "text_content": pending.get("text_content"),
        "notification_time": time_str
    }

    if day < 7:
        next_day = day + 1
        await state.update_data(current_day=next_day, schedule_data=sched_data, pending_content=None)
        await state.set_state(CustomScheduleStates.waiting_for_content)
        await message.answer(
            f"✅ Время для <b>{DAYS_INFO[day - 1][1]}</b> сохранено: <code>{time_str}</code>\n\n"
            + format_day_prompt(next_day),
            reply_markup=get_cancel_kb(),
            parse_mode="HTML"
        )
    else:
        await finish_custom_schedule(message, state, db_session, current_user, sched_data)


async def finish_custom_schedule(
    message: Message,
    state: FSMContext,
    db_session: AsyncSession,
    current_user: User,
    sched_data: Dict[int, Dict[str, Any]]
):
    await state.clear()

    user_id = current_user.id if current_user else None
    user_tg_id = message.from_user.id

    saved = await save_user_custom_schedules(
        session=db_session,
        user_tg_id=user_tg_id,
        user_id=user_id,
        days_data=sched_data
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Посмотреть расписание", callback_data="custom_sched_view")],
            [InlineKeyboardButton(text="⚙️ К настройкам", callback_data="open_settings")]
        ]
    )

    await message.answer(
        "<b>Расписание сохранено ✅</b>\n\n"
        "Теперь бот будет автоматически отправлять вам расписание в указанное время.",
        reply_markup=kb,
        parse_mode="HTML"
    )
