from datetime import date
from typing import Tuple, Optional

# Vacation intervals for 2026-2027 academic year (inclusive)
VACATIONS = [
    (date(2026, 1, 1), date(2026, 8, 31), "Летние каникулы"),
    (date(2026, 9, 1), date(2026, 9, 1), "1 Сентября (День знаний)"),
    (date(2026, 10, 26), date(2026, 11, 3), "Осенние каникулы"),
    (date(2026, 12, 31), date(2027, 1, 10), "Зимние каникулы"),
    (date(2027, 3, 27), date(2027, 4, 4), "Весенние каникулы"),
    (date(2027, 5, 27), date(2027, 8, 31), "Летние каникулы"),
]

# Working Saturdays (e.g. 20 February 2027)
WORKING_SATURDAYS = {
    date(2027, 2, 20)
}

def get_day_special_status(target_date: date) -> Tuple[str, str]:
    """
    Returns (status_type, description)
    status_type:
      - 'vacation': School vacation or holiday without lessons
      - 'working_weekend': Working Saturday (20.02.2027)
      - 'weekend': Saturday or Sunday
      - 'regular': Normal school day
    """
    # 0. Summer vacation before academic year starts
    if target_date < date(2026, 9, 1):
        return "vacation", "Летние каникулы"

    # 1. September 1st (Knowledge Day — no lessons)
    if target_date == date(2026, 9, 1):
        return "vacation", "1 Сентября (День знаний)"

    # 2. Check vacations first
    for start_d, end_d, name in VACATIONS:
        if start_d <= target_date <= end_d:
            return "vacation", name

    # 3. Check working Saturday
    if target_date in WORKING_SATURDAYS:
        return "working_weekend", "Рабочая суббота (перенос)"

    # 4. Check weekends (6 = Saturday, 7 = Sunday)
    if target_date.isoweekday() in (6, 7):
        day_name = "Суббота" if target_date.isoweekday() == 6 else "Воскресенье"
        return "weekend", f"Выходной ({day_name})"

    return "regular", ""

def format_day_badge(target_date: date, day_num: int, is_today: bool) -> str:
    """
    Returns formatted button label for calendar cell:
      - Today: •15•
      - September 1st: 🔔1
      - Vacation: 🌴15
      - Weekend: 🔴15
      - Working Saturday: 💼20
      - Regular: 15
    """
    if is_today:
        return f"•{day_num}•"

    if target_date == date(2026, 9, 1):
        return f"🔔{day_num}"

    status, _ = get_day_special_status(target_date)
    if status == "vacation":
        return f"🌴{day_num}"
    elif status == "working_weekend":
        return f"💼{day_num}"
    else:
        return str(day_num)

