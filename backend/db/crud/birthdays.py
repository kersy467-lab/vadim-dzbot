import logging
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import StudentBirthday

logger = logging.getLogger(__name__)

# Полный список 25 учеников 11 «Б» класса с датами рождения
DEFAULT_BIRTHDAYS = [
    {"full_name": "Дарина", "birth_day": 17, "birth_month": 6},
    {"full_name": "Айгиз", "birth_day": 3, "birth_month": 8},
    {"full_name": "Андрей", "birth_day": 8, "birth_month": 3},
    {"full_name": "Коля", "birth_day": 28, "birth_month": 12},
    {"full_name": "Илья", "birth_day": 25, "birth_month": 12},
    {"full_name": "Алмаз", "birth_day": 21, "birth_month": 4},
    {"full_name": "Тимур", "birth_day": 15, "birth_month": 12},
    {"full_name": "Миша", "birth_day": 29, "birth_month": 4},
    {"full_name": "Арина", "birth_day": 10, "birth_month": 7},
    {"full_name": "Глеб", "birth_day": 16, "birth_month": 9},
    {"full_name": "Исайкин", "birth_day": 23, "birth_month": 9},
    {"full_name": "Ильнара", "birth_day": 31, "birth_month": 5},
    {"full_name": "Сабрина", "birth_day": 11, "birth_month": 7},
    {"full_name": "Полина", "birth_day": 10, "birth_month": 7},
    {"full_name": "Матвей", "birth_day": 12, "birth_month": 2},
    {"full_name": "Игорь", "birth_day": 2, "birth_month": 6},
    {"full_name": "Никита", "birth_day": 6, "birth_month": 2},
    {"full_name": "Арслан", "birth_day": 17, "birth_month": 3},
    {"full_name": "Вадим", "birth_day": 26, "birth_month": 2},
    {"full_name": "Данияр", "birth_day": 2, "birth_month": 2},
    {"full_name": "Макар", "birth_day": 27, "birth_month": 10},
    {"full_name": "Эрик", "birth_day": 22, "birth_month": 11},
    {"full_name": "Эмилия", "birth_day": 28, "birth_month": 3},
    {"full_name": "Кирилл", "birth_day": 10, "birth_month": 5},
    {"full_name": "Родион", "birth_day": 7, "birth_month": 3},
]

MONTH_NAMES_GENITIVE = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

MONTH_NAMES_NOMINATIVE = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


async def seed_default_birthdays(session: AsyncSession) -> int:
    """Заполняет базу данных 25 учениками 11 «Б», если таблица пуста."""
    stmt = select(StudentBirthday).limit(1)
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is None:
        count = 0
        for item in DEFAULT_BIRTHDAYS:
            entry = StudentBirthday(
                full_name=item["full_name"],
                birth_day=item["birth_day"],
                birth_month=item["birth_month"]
            )
            session.add(entry)
            count += 1
        await session.commit()
        logger.info(f"Seeded {count} student birthdays for 11 «Б».")
        return count
    return 0


async def get_all_birthdays(session: AsyncSession) -> List[StudentBirthday]:
    """Возвращает всех учеников, отсортированных по месяцу и дню."""
    stmt = select(StudentBirthday).order_by(
        StudentBirthday.birth_month,
        StudentBirthday.birth_day,
        StudentBirthday.full_name
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_birthdays_for_date(
    session: AsyncSession,
    day: int,
    month: int
) -> List[StudentBirthday]:
    """Находит учеников, у которых день рождения выпадает на указанную дату."""
    stmt = select(StudentBirthday).where(
        StudentBirthday.birth_day == day,
        StudentBirthday.birth_month == month
    ).order_by(StudentBirthday.full_name)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_upcoming_birthdays(
    session: AsyncSession,
    from_date: date,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Находит ближайшие дни рождения относительно переданной даты from_date.
    Возвращает список словарей:
    [{"name": "...", "day": 16, "month": 9, "days_left": 4, "date_str": "16 сентября"}, ...]
    """
    all_b = await get_all_birthdays(session)
    if not all_b:
        return []

    result = []
    curr_year = from_date.year

    for b in all_b:
        try:
            b_date = date(curr_year, b.birth_month, b.birth_day)
        except ValueError:
            b_date = date(curr_year, 3, 1)

        if b_date < from_date:
            try:
                b_date = date(curr_year + 1, b.birth_month, b.birth_day)
            except ValueError:
                b_date = date(curr_year + 1, 3, 1)

        days_left = (b_date - from_date).days
        month_name = MONTH_NAMES_GENITIVE.get(b.birth_month, "")
        result.append({
            "name": b.full_name,
            "day": b.birth_day,
            "month": b.birth_month,
            "days_left": days_left,
            "date_str": f"{b.birth_day} {month_name}",
            "next_date": b_date
        })

    result.sort(key=lambda x: (x["days_left"], x["name"]))
    return result[:limit]
