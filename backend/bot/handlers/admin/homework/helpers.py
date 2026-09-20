import time
import asyncio
from datetime import date, datetime, timedelta
from typing import List, Tuple, Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User, Subject
from backend.db.crud import (
    get_all_subjects, get_subject_by_id, create_homework, delete_homework,
    get_recent_active_homeworks, get_homework_by_id, find_upcoming_dates_for_subject
)
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_hw_notify_keyboard
)
from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.services.notifier import send_new_homework_alert
from backend.bot.handlers.schedule import DAYS_RU
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.states import AddHomeworkStates

# ==================== HELPERS & FORMATTING ====================

SUBJECT_ICONS = {
    "Русский язык": "📖",
    "Литература": "📚",
    "Алгебра": "📐",
    "Геометрия": "📏",
    "Физика": "⚡",
    "Химия": "🧪",
    "Биология": "🌿",
    "История": "🏛",
    "Обществознание": "⚖️",
    "География": "🌍",
    "Английский язык": "🇬🇧",
    "Информатика": "💻",
    "Физкультура": "⚽",
    "ОБЖ": "🛡",
    "ВИС": "🎓",
}

SUBJECT_ALIASES = {
    "русский": "Русский язык",
    "русский язык": "Русский язык",
    "рус": "Русский язык",
    "рус яз": "Русский язык",
    "русяз": "Русский язык",
    "литература": "Литература",
    "литра": "Литература",
    "лит-ра": "Литература",
    "лит": "Литература",
    "алгебра": "Алгебра",
    "алг": "Алгебра",
    "математика": "Алгебра",
    "матеша": "Алгебра",
    "геометрия": "Геометрия",
    "геома": "Геометрия",
    "геом": "Геометрия",
    "физика": "Физика",
    "физ": "Физика",
    "химия": "Химия",
    "хим": "Химия",
    "биология": "Биология",
    "био": "Биология",
    "история": "История",
    "ист": "История",
    "обществознание": "Обществознание",
    "общество": "Обществознание",
    "общага": "Обществознание",
    "география": "География",
    "гео": "География",
    "английский": "Английский язык",
    "английский язык": "Английский язык",
    "англ": "Английский язык",
    "англ яз": "Английский язык",
    "инглиш": "Английский язык",
    "информатика": "Информатика",
    "инфа": "Информатика",
    "ит": "Информатика",
    "it": "Информатика",
    "информационные технологии": "Информатика",
    "физкультура": "Физкультура",
    "физра": "Физкультура",
    "спорт": "Физкультура",
    "обж": "ОБЖ",
    "основы безопасности": "ОБЖ",
    "вис": "ВИС",
}


def escape_md(text: str) -> str:
    r"""Экранирует спецсимволы Markdown v1: \, _, *, `, ["""
    if not text:
        return ""
    for ch in ["\\", "_", "*", "`", "["]:
        text = text.replace(ch, f"\\{ch}")
    return text


async def safe_answer(message: Message, text: str, reply_markup=None) -> Optional[Message]:
    """Отправляет сообщение с Markdown разметкой; при синтаксических ошибках откатывается к чистому тексту."""
    try:
        return await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        plain = text.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
        return await message.answer(plain, reply_markup=reply_markup, parse_mode=None)


async def safe_edit_text(message_or_query, text: str, reply_markup=None):
    """Редактирует сообщение с Markdown разметкой; при ошибках парсинга откатывается к чистому тексту."""
    msg = message_or_query.message if hasattr(message_or_query, "message") else message_or_query
    try:
        return await msg.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        plain = text.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
        return await msg.edit_text(plain, reply_markup=reply_markup, parse_mode=None)


def find_subject_by_text(text: str, subjects: List[Subject]) -> Optional[Subject]:
    """Находит предмет по точному совпадению, списку синонимов или частичному вхождению."""
    clean = text.strip().lower()
    if not clean:
        return None

    # 1. Проверяем словарь алиасов
    target_name = SUBJECT_ALIASES.get(clean)
    if target_name:
        for s in subjects:
            if s.name.lower() == target_name.lower():
                return s

    # 2. Точное совпадение (регистронезависимо)
    for s in subjects:
        if s.name.lower() == clean:
            return s

    # 3. Совпадение по началу или вхождению
    for s in subjects:
        s_low = s.name.lower()
        if clean in s_low or s_low in clean:
            return s

    return None


def build_subjects_keyboard_grid(subjects: List[Subject]) -> InlineKeyboardMarkup:
    """Генерирует компактную 2-колоночную клавиатуру выбора предметов с иконками."""
    buttons = []
    row = []
    for s in subjects:
        icon = SUBJECT_ICONS.get(s.name, "📚")
        btn = InlineKeyboardButton(text=f"{icon} {s.name}", callback_data=f"adm_hw_s_{s.id}")
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def is_saturday_physics(subject_name: Optional[str], target_date: date) -> bool:
    """Субботняя физика — отдельное занятие, на неё нельзя назначить ДЗ"""
    return bool(subject_name and subject_name.strip().lower() == "физика" and target_date.isoweekday() == 6)


async def get_upcoming_or_fallback_dates(
    db_session: AsyncSession,
    subject_id: int,
    from_date: date,
    limit: int = 4
) -> Tuple[List[date], bool]:
    """
    Возвращает (список_дат, есть_ли_в_расписании).
    Если предмет стоит в расписании уроков, возвращает дни уроков.
    Если расписание для предмета не заполнено (или уроков меньше limit),
    дополняет ближайшими учебными днями (Пн-Сб, пропуская Вс и субботу для физики).
    """
    scheduled = await find_upcoming_dates_for_subject(db_session, subject_id, from_date=from_date, limit=limit)
    is_scheduled = bool(scheduled)
    dates = list(scheduled)

    subj = await get_subject_by_id(db_session, subject_id)
    is_physics = bool(subj and subj.name.strip().lower() == "физика")

    cur = from_date
    while len(dates) < limit:
        # Пропускаем выходные (субботу 6 и воскресенье 7) — для ДЗ пятидневка
        if cur.isoweekday() not in (6, 7) and cur not in dates:
            dates.append(cur)
        cur += timedelta(days=1)

    dates.sort()
    return dates, is_scheduled


def build_date_keyboard(dates: List[date], selected_date: date, is_scheduled: bool) -> InlineKeyboardMarkup:
    """Строит инлайн-клавиатуру выбора дат сдачи."""
    date_btns = []
    for i, d in enumerate(dates):
        d_name = DAYS_RU.get(d.isoweekday(), "")
        is_cur = (d == selected_date)
        if is_cur:
            icon = "✅"
        elif i == 0 and is_scheduled:
            icon = "⭐"
        else:
            icon = "📅"
        suffix = " — След. урок" if (i == 0 and is_scheduled) else ""
        label = f"{icon} {d_name} ({d.strftime('%d.%m')}){suffix}"
        date_btns.append([InlineKeyboardButton(text=label, callback_data=f"adm_hw_d_{d.isoformat()}")])

    date_btns.append([InlineKeyboardButton(text="🗓 Другая дата на календаре", callback_data="adm_hw_open_cal")])
    date_btns.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=date_btns)


async def proceed_to_entering_content(
    target_msg,  # CallbackQuery or Message
    state: FSMContext,
    db_session: AsyncSession,
    subject_id: int
):
    """Общий переход к шагу ввода задания после выбора предмета (кнопкой или текстом)."""
    subj = await get_subject_by_id(db_session, subject_id)
    subj_name = subj.name if subj else "Предмет"

    from backend.config import get_today
    today = get_today()

    dates, is_sched = await get_upcoming_or_fallback_dates(
        db_session, subject_id, from_date=today + timedelta(days=1), limit=4
    )

    if not is_sched:
        # Урока нет в будущем расписании — НЕ ставим на завтра по умолчанию!
        await state.update_data(
            subject_id=subject_id,
            due_date=None,
            assigned_date=today.isoformat(),
            attachments=[],
            description=""
        )
        await state.set_state(AddHomeworkStates.entering_date)
        kb = get_inline_calendar("adm_hw", year=today.year, month=today.month, back_callback="admin_cancel")
        text = (
            f"📚 **Добавление ДЗ — {subj_name}**\n\n"
            "⚠️ **Этого предмета нет в будущем расписании уроков.**\n"
            "Бот не стал автоматически назначать сдачу на завтра.\n\n"
            "📅 **Пожалуйста, выберите дату сдачи на календаре:**"
        )
        if isinstance(target_msg, CallbackQuery):
            await safe_edit_text(target_msg.message, text, reply_markup=kb)
            try:
                await target_msg.answer()
            except Exception:
                pass
        else:
            await safe_answer(target_msg, text, reply_markup=kb)
        return

    default_d = dates[0] if dates else (today + timedelta(days=1))

    await state.update_data(
        subject_id=subject_id,
        due_date=default_d.isoformat(),
        assigned_date=today.isoformat(),
        attachments=[],
        description=""
    )
    await state.set_state(AddHomeworkStates.entering_content)

    d_name = DAYS_RU.get(default_d.isoweekday(), "")
    sched_hint = " *(следующий урок)*" if is_sched else ""
    text = (
        f"📚 **Добавление ДЗ — {subj_name}**\n\n"
        f"📅 **Дата сдачи (следующий урок в расписании):**\n"
        f"👉 **{d_name}, {default_d.strftime('%d.%m.%Y')}**{sched_hint}\n\n"
        "✍️ **Отправьте задание в чат:**\n"
        "• Текстом (номера упражнений, параграфы)\n"
        "• Либо фото/документами (можно отправить сразу несколько файлов!)\n\n"
        "*(Если нужно задать на другой день — выберите дату кнопками ниже)*:"
    )

    kb = build_date_keyboard(dates, selected_date=default_d, is_scheduled=is_sched)

    if isinstance(target_msg, CallbackQuery):
        await safe_edit_text(target_msg.message, text, reply_markup=kb)
        try:
            await target_msg.answer()
        except Exception:
            pass
    else:
        await safe_answer(target_msg, text, reply_markup=kb)


