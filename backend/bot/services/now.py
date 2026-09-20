import logging
import zoneinfo
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.crud.schedule import get_schedule_for_date, get_substitutions_for_date
from backend.db.crud.bells import get_bell_schedule_for_date
from backend.bot.services.academic_calendar import get_day_special_status

logger = logging.getLogger(__name__)

DAYS_RU = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье"
}

DAYS_PREP_RU = {
    1: "В понедельник",
    2: "Во вторник",
    3: "В среду",
    4: "В четверг",
    5: "В пятницу",
    6: "В субботу",
    7: "В воскресенье"
}


@dataclass
class LessonSlot:
    lesson_number: int
    subject_name: str
    start_time: str
    end_time: str
    start_minutes: int
    end_minutes: int


def time_to_minutes(time_str: str) -> Optional[int]:
    """Переводит строку 'HH:MM' в количество минут от полуночи."""
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None


def format_duration_ru(mins: int) -> str:
    """Склоняет минуты и часы по правилам русского языка."""
    if mins <= 0:
        return "менее 1 минуты"
    if mins < 60:
        rem100 = mins % 100
        rem10 = mins % 10
        if 11 <= rem100 <= 19:
            unit = "минут"
        elif rem10 == 1:
            unit = "минута"
        elif 2 <= rem10 <= 4:
            unit = "минуты"
        else:
            unit = "минут"
        return f"{mins} {unit}"

    hours = mins // 60
    rem = mins % 60
    h100 = hours % 100
    h10 = hours % 10
    if 11 <= h100 <= 19:
        h_unit = "часов"
    elif h10 == 1:
        h_unit = "час"
    elif 2 <= h10 <= 4:
        h_unit = "часа"
    else:
        h_unit = "часов"

    if rem == 0:
        return f"{hours} {h_unit}"
    return f"{hours} {h_unit} {rem} мин"


def format_lessons_count_ru(count: int) -> str:
    """Склоняет слово 'урок' (1 урок, 2 урока, 5 уроков)."""
    rem100 = count % 100
    rem10 = count % 10
    if 11 <= rem100 <= 19:
        unit = "уроков"
    elif rem10 == 1:
        unit = "урок"
    elif 2 <= rem10 <= 4:
        unit = "урока"
    else:
        unit = "уроков"
    return f"{count} {unit}"


async def get_effective_lessons_for_date(session: AsyncSession, target_date: date) -> List[LessonSlot]:
    """Собирает список активных уроков на дату с учетом замен и звонков."""
    schedules = await get_schedule_for_date(session, target_date)
    subs = {s.lesson_number: s for s in await get_substitutions_for_date(session, target_date)}
    bells = {b.lesson_number: b for b in await get_bell_schedule_for_date(session, target_date)}

    sched_map = {s.lesson_number: s for s in schedules}
    all_numbers = sorted(set(list(sched_map.keys()) + list(subs.keys())))

    slots: List[LessonSlot] = []
    for num in all_numbers:
        bell = bells.get(num)
        base = sched_map.get(num)
        sub = subs.get(num)

        start_str = base.start_time if base and base.start_time else (bell.start_time if bell else None)
        end_str = base.end_time if base and base.end_time else (bell.end_time if bell else None)

        if not start_str or not end_str:
            continue

        start_min = time_to_minutes(start_str)
        end_min = time_to_minutes(end_str)
        if start_min is None or end_min is None:
            continue

        if sub:
            if sub.is_cancelled:
                continue
            subject_name = sub.new_subject.name if sub.new_subject else (base.subject.name if base and base.subject else "Урок")
        elif base and base.subject:
            subject_name = base.subject.name
        else:
            continue

        slots.append(LessonSlot(
            lesson_number=num,
            subject_name=subject_name,
            start_time=start_str,
            end_time=end_str,
            start_minutes=start_min,
            end_minutes=end_min
        ))

    return slots


async def find_next_school_day(session: AsyncSession, from_date: date) -> Optional[Tuple[date, List[LessonSlot]]]:
    """Ищет ближайший следующий учебный день с уроками в пределах 7 дней."""
    for delta in range(1, 8):
        check_date = from_date + timedelta(days=delta)
        status, _ = get_day_special_status(check_date)
        if status == "vacation":
            continue
        slots = await get_effective_lessons_for_date(session, check_date)
        if slots:
            return check_date, slots
    return None


async def get_now_lesson_status(session: AsyncSession, now_dt: Optional[datetime] = None) -> str:
    """Формирует понятный текст текущего статуса для команды /now."""
    if now_dt is None:
        try:
            tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
            now_dt = datetime.now(tz)
        except Exception:
            now_dt = datetime.now()

    today = now_dt.date()
    now_minutes = now_dt.hour * 60 + now_dt.minute

    slots = await get_effective_lessons_for_date(session, today)

    # 1. Если сегодня уроков нет вообще (каникулы, выходной или пусто)
    if not slots:
        status, status_text = get_day_special_status(today)
        if status == "vacation":
            header = f"🌴 **Сегодня каникулы: {status_text}!**\nОтдыхаем и набираемся сил."
        elif status == "weekend":
            day_title = DAYS_RU.get(today.isoweekday(), "выходной")
            header = f"🏖️ **Сегодня выходной ({day_title})!**\nОтдыхаем."
        else:
            header = "🎉 **На сегодня уроков в расписании нет.**\nОтдыхаем и занимаемся своими делами!"

        lines = [header]
        next_info = await find_next_school_day(session, today)
        if next_info:
            next_date, next_slots = next_info
            first_s = next_slots[0]
            prep_day = DAYS_PREP_RU.get(next_date.isoweekday(), "В учебный день")
            date_str = next_date.strftime("%d.%m")
            lines.append(f"\n📅 **{prep_day} ({date_str}):** 1-й урок — {first_s.subject_name} в {first_s.start_time}")
        return "\n".join(lines)

    first_slot = slots[0]
    last_slot = slots[-1]

    # 2. Утро до начала уроков
    if now_minutes < first_slot.start_minutes:
        diff = first_slot.start_minutes - now_minutes
        t_left = format_duration_ru(diff)
        lines = [
            "🌅 **Уроки ещё не начались**\n",
            f"⏳ **До 1-го урока:** `{t_left}` (звонок в {first_slot.start_time})",
            f"🔔 **1-й урок ({first_slot.lesson_number}-й):** {first_slot.subject_name}",
            f"📋 **Всего сегодня:** {format_lessons_count_ru(len(slots))} (до {last_slot.end_time})"
        ]
        return "\n".join(lines)

    # 3. Во время какого-то урока
    for idx, curr_slot in enumerate(slots):
        if curr_slot.start_minutes <= now_minutes < curr_slot.end_minutes:
            diff = curr_slot.end_minutes - now_minutes
            t_left = format_duration_ru(diff)
            lines = [
                f"🔔 **Сейчас ({curr_slot.lesson_number}-й урок):** {curr_slot.subject_name}",
                f"⏳ **До конца урока:** `{t_left}` (звонок в {curr_slot.end_time})"
            ]
            if idx + 1 < len(slots):
                next_slot = slots[idx + 1]
                break_min = next_slot.start_minutes - curr_slot.end_minutes
                lines.append(f"🔜 **Следующий урок ({next_slot.lesson_number}-й):** {next_slot.subject_name} (перемена {break_min} мин)")
            else:
                lines.append("🏁 **Это последний урок на сегодня!** Дальше домой.")
            return "\n".join(lines)

    # 4. На перемене между уроками
    for i in range(len(slots) - 1):
        if slots[i].end_minutes <= now_minutes < slots[i + 1].start_minutes:
            prev_slot = slots[i]
            next_slot = slots[i + 1]
            diff = next_slot.start_minutes - now_minutes
            t_left = format_duration_ru(diff)
            break_total = next_slot.start_minutes - prev_slot.end_minutes
            lines = [
                "☕ **Сейчас перемена!**\n",
                f"⏳ **До звонка на урок:** `{t_left}` (перемена {break_total} мин)",
                f"🔜 **Следующий урок ({next_slot.lesson_number}-й):** {next_slot.subject_name} (звонок в {next_slot.start_time})",
                f"🚪 _Предыдущий урок:_ {prev_slot.subject_name} завершён"
            ]
            return "\n".join(lines)

    # 5. Вечер после окончания всех уроков
    lines = [
        "🏠 **Уроки на сегодня всё!**\n",
        f"🎒 Все {format_lessons_count_ru(len(slots))} завершены в {last_slot.end_time}."
    ]
    next_info = await find_next_school_day(session, today)
    if next_info:
        next_date, next_slots = next_info
        first_s = next_slots[0]
        if next_date == today + timedelta(days=1):
            day_label = f"Завтра ({DAYS_RU.get(next_date.isoweekday(), '')})"
        else:
            day_label = f"{DAYS_PREP_RU.get(next_date.isoweekday(), '')} ({next_date.strftime('%d.%m')})"
        lines.append(f"📅 **{day_label}:** 1-й урок — {first_s.subject_name} в {first_s.start_time}")

    lines.append("📝 _Подсказка: проверить заданную домашку можно по кнопке «📚 Домашка»_")
    return "\n".join(lines)
