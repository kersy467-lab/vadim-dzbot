from datetime import date, timedelta
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.db.models import Subject

def get_schedule_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="⚡ Сегодня", callback_data="sched_today"),
            InlineKeyboardButton(text="➡️ Завтра", callback_data="sched_tomorrow")
        ],
        [
            InlineKeyboardButton(text="📅 Вся неделя", callback_data="sched_week"),
            InlineKeyboardButton(text="🔔 Звонки", callback_data="sched_bells")
        ],
        [
            InlineKeyboardButton(text="🗓 Выбрать дату (Календарь)", callback_data="sched_calendar")
        ]
    ]
    if is_admin:
        rows.append([
            InlineKeyboardButton(text="📢 Скинуть расписание", callback_data="admin_broadcast_schedule")
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_day_picker_keyboard() -> InlineKeyboardMarkup:
    days = [
        ("Пн", 1), ("Вт", 2), ("Ср", 3),
        ("Чт", 4), ("Пт", 5), ("Сб", 6)
    ]
    rows = []
    current_row = []
    for name, d_num in days:
        current_row.append(InlineKeyboardButton(text=name, callback_data=f"sched_day_{d_num}"))
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="sched_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_homework_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ На завтра", callback_data="hw_tomorrow"),
                InlineKeyboardButton(text="📅 На конкретный день", callback_data="hw_pick_date")
            ],
            [
                InlineKeyboardButton(text="📖 По предмету", callback_data="hw_by_subject"),
                InlineKeyboardButton(text="📝 Мой чеклист", callback_data="hw_my_tasks")
            ]
        ]
    )

def get_subjects_keyboard(subjects: List[Subject], prefix: str = "hw_subj_") -> InlineKeyboardMarkup:
    rows = []
    for subj in subjects:
        rows.append([InlineKeyboardButton(text=subj.name, callback_data=f"{prefix}{subj.id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_homework_item_keyboard(hw_id: int, is_done: bool) -> InlineKeyboardMarkup:
    status_text = "✅ Сделано (отметить не сделанным)" if is_done else "⬜ Отметить сделанным"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=status_text, callback_data=f"hw_toggle_{hw_id}")]
        ]
    )

def get_admin_approval_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_{tg_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{tg_id}")
            ]
        ]
    )

def get_settings_keyboard(notifications_enabled: bool) -> InlineKeyboardMarkup:
    bell_status = "🔔 Включены" if notifications_enabled else "🔕 Выключены"
    toggle_btn_text = "Выключить уведомления" if notifications_enabled else "Включить уведомления"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Вечерние напоминания: {bell_status}",
                    callback_data="noop"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🔄 {toggle_btn_text}",
                    callback_data="toggle_notifications"
                )
            ]
        ]
    )
