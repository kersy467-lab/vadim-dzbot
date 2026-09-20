from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import BellSchedule


def _time_to_minutes(t_str: str) -> int:
    try:
        parts = t_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0


def _minutes_to_time(mins: int) -> str:
    h = (mins // 60) % 24
    m = mins % 60
    return f"{h:02d}:{m:02d}"


async def recalculate_bell_schedule_chain(
    session: AsyncSession,
    specific_date: Optional[date] = None,
    from_lesson: int = 2
) -> List[BellSchedule]:
    """
    Автоматически пересчитывает цепочку времени уроков на основе длительности перемен:
    Время начала урока i+1 = Время окончания урока i + перемена после урока i.
    Длительность самого урока сохраняется.
    """
    query = select(BellSchedule)
    if specific_date is not None:
        query = query.where(BellSchedule.specific_date == specific_date)
    else:
        query = query.where(BellSchedule.specific_date.is_(None))

    query = query.order_by(BellSchedule.lesson_number.asc())
    result = await session.execute(query)
    bells = list(result.scalars().all())

    if not bells:
        return []

    bell_map = {b.lesson_number: b for b in bells}
    sorted_numbers = sorted(bell_map.keys())

    for idx, l_num in enumerate(sorted_numbers):
        if l_num < from_lesson or idx == 0:
            continue

        prev_num = sorted_numbers[idx - 1]
        prev_bell = bell_map[prev_num]
        cur_bell = bell_map[l_num]

        prev_end_min = _time_to_minutes(prev_bell.end_time)
        break_mins = prev_bell.break_duration if prev_bell.break_duration is not None else 10

        cur_start_min = _time_to_minutes(cur_bell.start_time)
        cur_end_min = _time_to_minutes(cur_bell.end_time)
        cur_duration = cur_end_min - cur_start_min
        if cur_duration <= 0 or cur_duration > 180:
            cur_duration = 40

        new_start_min = prev_end_min + break_mins
        new_end_min = new_start_min + cur_duration

        cur_bell.start_time = _minutes_to_time(new_start_min)
        cur_bell.end_time = _minutes_to_time(new_end_min)

    await session.commit()
    for b in bells:
        await session.refresh(b)
    return bells


async def set_bell_break_duration(
    session: AsyncSession,
    lesson_number: int,
    break_duration: int,
    specific_date: Optional[date] = None
) -> Optional[BellSchedule]:
    query = select(BellSchedule).where(BellSchedule.lesson_number == lesson_number)
    if specific_date is not None:
        query = query.where(BellSchedule.specific_date == specific_date)
    else:
        query = query.where(BellSchedule.specific_date.is_(None))

    result = await session.execute(query)
    item = result.scalar_one_or_none()
    if item:
        item.break_duration = break_duration
        await session.commit()
        # Автоматически пересчитываем время всех последующих уроков!
        await recalculate_bell_schedule_chain(session, specific_date=specific_date, from_lesson=lesson_number + 1)
        await session.refresh(item)
    return item


async def get_bell_schedule(session: AsyncSession) -> List[BellSchedule]:
    """Постоянное расписание звонков (без привязки к конкретной дате)"""
    result = await session.execute(
        select(BellSchedule)
        .where(BellSchedule.specific_date.is_(None))
        .order_by(BellSchedule.lesson_number)
    )
    return list(result.scalars().all())


async def get_bell_schedule_for_date(session: AsyncSession, target_date: date) -> List[BellSchedule]:
    """
    Возвращает звонки на конкретную дату:
    1. Ищет звонки, привязанные к specific_date == target_date.
    2. Если нет — возвращает постоянное расписание звонков.
    """
    res_date = await session.execute(
        select(BellSchedule)
        .where(BellSchedule.specific_date == target_date)
        .order_by(BellSchedule.lesson_number)
    )
    date_items = list(res_date.scalars().all())
    if date_items:
        return date_items
    return await get_bell_schedule(session)


async def set_bell_schedule_item(
    session: AsyncSession,
    lesson_number: int,
    start_time: str,
    end_time: str,
    break_duration: int = 10,
    specific_date: Optional[date] = None
) -> BellSchedule:
    query = select(BellSchedule).where(BellSchedule.lesson_number == lesson_number)
    if specific_date is not None:
        query = query.where(BellSchedule.specific_date == specific_date)
    else:
        query = query.where(BellSchedule.specific_date.is_(None))

    result = await session.execute(query)
    item = result.scalar_one_or_none()
    if item:
        item.start_time = start_time
        item.end_time = end_time
        item.break_duration = break_duration
    else:
        item = BellSchedule(
            specific_date=specific_date,
            lesson_number=lesson_number,
            start_time=start_time,
            end_time=end_time,
            break_duration=break_duration
        )
        session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def clear_date_bells(session: AsyncSession, target_date: date):
    """Удаляет звонки на конкретную дату, возвращая день к стандартным звонкам"""
    await session.execute(delete(BellSchedule).where(BellSchedule.specific_date == target_date))
    await session.commit()


async def save_bulk_date_bells(
    session: AsyncSession,
    target_date: date,
    bells: List[Tuple[int, str, str, int]]
) -> List[BellSchedule]:
    await clear_date_bells(session, target_date)
    saved = []
    for l_num, start_t, end_t, brk in bells:
        item = await set_bell_schedule_item(
            session=session,
            lesson_number=l_num,
            start_time=start_t,
            end_time=end_t,
            break_duration=brk,
            specific_date=target_date
        )
        saved.append(item)
    return saved
