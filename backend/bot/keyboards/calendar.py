import calendar
from datetime import date, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from backend.bot.services.academic_calendar import format_day_badge

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

DAYS_HEADER = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def get_inline_calendar(
    action: str,
    year: int | None = None,
    month: int | None = None,
    back_callback: str | None = None
) -> InlineKeyboardMarkup:
    """
    Creates an interactive inline calendar keyboard with:
    - Special markers: 🌴 (Каникулы), 🔴 (Выходные), 💼 (Рабочая суббота 20.02.2027), •• (Сегодня).
    """
    today = date.today()
    if year is None or month is None:
        year = today.year
        month = today.month

    # Prev / Next month calculations
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1

    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    keyboard = []

    # 1. Header: Month, Year and Nav Buttons
    month_name = MONTHS_RU.get(month, "")
    keyboard.append([
        InlineKeyboardButton(text="◀️", callback_data=f"cal_nav_{action}_{prev_year}_{prev_month}"),
        InlineKeyboardButton(text=f"📅 {month_name} {year}", callback_data="cal_ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"cal_nav_{action}_{next_year}_{next_month}")
    ])

    # 2. Weekdays Header
    keyboard.append([
        InlineKeyboardButton(text=d, callback_data="cal_ignore") for d in DAYS_HEADER
    ])

    # 3. Days Grid
    month_matrix = calendar.monthcalendar(year, month)
    for week in month_matrix:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal_ignore"))
            else:
                cell_date = date(year, month, day)
                is_today = (cell_date == today)
                btn_text = format_day_badge(cell_date, day, is_today)
                cb_data = f"cal_act_{action}_{year}_{month:02d}_{day:02d}"
                row.append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
        keyboard.append(row)

    # 4. Quick Select Row (Сегодня / Завтра)
    tomorrow = today + timedelta(days=1)
    quick_row = [
        InlineKeyboardButton(
            text="⚡ Сегодня",
            callback_data=f"cal_act_{action}_{today.year}_{today.month:02d}_{today.day:02d}"
        ),
        InlineKeyboardButton(
            text="➡️ Завтра",
            callback_data=f"cal_act_{action}_{tomorrow.year}_{tomorrow.month:02d}_{tomorrow.day:02d}"
        )
    ]
    keyboard.append(quick_row)

    # 5. Back Button
    if back_callback:
        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
