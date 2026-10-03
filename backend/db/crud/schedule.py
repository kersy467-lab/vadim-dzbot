from datetime import date, timedelta
from typing import List, Optional, Tuple, Dict
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.models import Schedule, Substitution, Subject
from backend.db.crud.subjects import get_or_create_subject


async def get_permanent_schedule_for_day(session: AsyncSession, day_of_week: int) -> List[Schedule]:
    result = await session.execute(
        select(Schedule)
        .options(joinedload(Schedule.subject))
        .where(Schedule.specific_date.is_(None), Schedule.day_of_week == day_of_week)
        .order_by(Schedule.lesson_number)
    )
    return list(result.scalars().all())


async def get_schedule_for_day(session: AsyncSession, day_of_week: int) -> List[Schedule]:
    """Псевдоним для постоянного расписания по дню недели"""
    return await get_permanent_schedule_for_day(session, day_of_week)


def is_extracurricular_lesson(day_of_week: int, lesson_number: int, subject_name: Optional[str] = None) -> bool:
    """Внеурочные занятия: субботняя физика (1 ур), русский в Пн (8 ур), математика в Пт (9 ур)."""
    if day_of_week == 6 and lesson_number == 1:
        return True
    if day_of_week == 1 and lesson_number == 8:
        return True
    if day_of_week == 5 and lesson_number == 9:
        return True
    if subject_name:
        s = subject_name.strip().lower()
        if s == "физика" and day_of_week == 6:
            return True
        if s == "математика":
            return True
        if s == "русский язык" and day_of_week == 1 and lesson_number == 8:
            return True
    return False


async def get_schedule_for_date(session: AsyncSession, target_date: date) -> List[Schedule]:
    """
    Возвращает расписание на конкретную дату:
    1. Если дата 1 сентября 2026 или ранее — уроков не было, возвращает пустой список.
    2. Сначала ищет уроки, явно привязанные к этой дате (specific_date == target_date).
    3. Если на эту дату уроков не задано, возвращает постоянное расписание для дня недели (specific_date is None).
    4. Если на дату заданы индивидуальные уроки, но в них не указаны постоянные внеурочные занятия
       (например, 8-й урок русского в Пн, 9-й урок математики в Пт, субботняя физика),
       они автоматически подтягиваются из постоянного расписания, если не были отменены заменой.
    """
    if target_date <= date(2026, 9, 1):
        return []

    day_of_week = target_date.isoweekday()
    perm_lessons = await get_permanent_schedule_for_day(session, day_of_week)

    res_date = await session.execute(
        select(Schedule)
        .options(joinedload(Schedule.subject))
        .where(Schedule.specific_date == target_date)
        .order_by(Schedule.lesson_number)
    )
    date_items = list(res_date.scalars().all())
    if not date_items:
        return perm_lessons

    date_lesson_nums = {item.lesson_number for item in date_items}
    extra_items = []
    for p in perm_lessons:
        s_name = p.subject.name if p.subject else None
        if p.lesson_number not in date_lesson_nums and is_extracurricular_lesson(day_of_week, p.lesson_number, s_name):
            extra_items.append(p)

    if extra_items:
        return sorted(date_items + extra_items, key=lambda x: x.lesson_number)

    return date_items


async def get_full_week_schedule(session: AsyncSession) -> Dict[int, List[Schedule]]:
    """Постоянное расписание на всю неделю (1..7)"""
    result = await session.execute(
        select(Schedule)
        .options(joinedload(Schedule.subject))
        .where(Schedule.specific_date.is_(None))
        .order_by(Schedule.day_of_week, Schedule.lesson_number)
    )
    all_items = result.scalars().all()
    week_map: Dict[int, List[Schedule]] = {d: [] for d in range(1, 8)}
    for item in all_items:
        week_map[item.day_of_week].append(item)
    return week_map


async def set_schedule_item(
    session: AsyncSession,
    day_of_week: int,
    lesson_number: int,
    subject_id: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    specific_date: Optional[date] = None
) -> Schedule:
    query = select(Schedule).where(Schedule.lesson_number == lesson_number)
    if specific_date is not None:
        query = query.where(Schedule.specific_date == specific_date)
    else:
        query = query.where(Schedule.specific_date.is_(None), Schedule.day_of_week == day_of_week)

    result = await session.execute(query)
    item = result.scalar_one_or_none()
    if item:
        item.subject_id = subject_id
        item.start_time = start_time
        item.end_time = end_time
    else:
        item = Schedule(
            specific_date=specific_date,
            day_of_week=day_of_week,
            lesson_number=lesson_number,
            subject_id=subject_id,
            start_time=start_time,
            end_time=end_time
        )
        session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def freeze_past_schedules_for_weekday(
    session: AsyncSession,
    day_of_week: int,
    up_to_date: Optional[date] = None
):
    """
    Замораживает историю расписания для прошлых дат этого дня недели.
    Если на прошлые даты не было индивидуального расписания, текущее постоянное расписание
    сохраняется для них как снимок (specific_date = past_date), чтобы последующее изменение
    постоянного расписания повлияло ТОЛЬКО на будущее, а в прошлом осталась история.
    Учебный год с уроками начинается со 2 сентября 2026 (среда); 1 сентября и ранее уроков не было.
    """
    from backend.config import get_today
    if up_to_date is None:
        today = get_today()
        # Замораживаем только завершенные прошедшие недели (до понедельника текущей недели)!
        # Текущая неделя НЕ должна замораживаться автоматически как прошлое.
        up_to_date = today - timedelta(days=today.isoweekday() - 1)

    start_date = date(2026, 9, 2)
    if up_to_date <= start_date:
        return

    curr_lessons = await get_permanent_schedule_for_day(session, day_of_week)
    if not curr_lessons:
        return

    curr_d = start_date
    delta = (day_of_week - curr_d.isoweekday()) % 7
    curr_d += timedelta(days=delta)

    while curr_d < up_to_date:
        if curr_d <= date(2026, 9, 1):
            curr_d += timedelta(days=7)
            continue

        res = await session.execute(
            select(Schedule).where(Schedule.specific_date == curr_d)
        )
        existing_on_date = res.scalars().all()
        if not existing_on_date:
            for l in curr_lessons:
                snapshot = Schedule(
                    specific_date=curr_d,
                    day_of_week=day_of_week,
                    lesson_number=l.lesson_number,
                    subject_id=l.subject_id,
                    start_time=l.start_time,
                    end_time=l.end_time
                )
                session.add(snapshot)
        curr_d += timedelta(days=7)

    await session.commit()


async def set_permanent_schedule_item(
    session: AsyncSession,
    day_of_week: int,
    lesson_number: int,
    subject_id: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
) -> Schedule:
    await freeze_past_schedules_for_weekday(session, day_of_week)
    return await set_schedule_item(
        session=session,
        day_of_week=day_of_week,
        lesson_number=lesson_number,
        subject_id=subject_id,
        start_time=start_time,
        end_time=end_time,
        specific_date=None
    )


async def set_date_schedule_item(
    session: AsyncSession,
    target_date: date,
    lesson_number: int,
    subject_id: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
) -> Schedule:
    return await set_schedule_item(
        session=session,
        day_of_week=target_date.isoweekday(),
        lesson_number=lesson_number,
        subject_id=subject_id,
        start_time=start_time,
        end_time=end_time,
        specific_date=target_date
    )


async def delete_date_schedule_item(session: AsyncSession, target_date: date, lesson_number: int):
    await session.execute(
        delete(Schedule).where(
            Schedule.specific_date == target_date,
            Schedule.lesson_number == lesson_number
        )
    )
    await session.commit()


async def clear_date_schedule(session: AsyncSession, target_date: date):
    await session.execute(delete(Schedule).where(Schedule.specific_date == target_date))
    await session.commit()


async def clear_permanent_day_schedule(session: AsyncSession, day_of_week: int):
    await freeze_past_schedules_for_weekday(session, day_of_week)
    await session.execute(
        delete(Schedule).where(Schedule.specific_date.is_(None), Schedule.day_of_week == day_of_week)
    )
    await session.commit()


async def save_bulk_date_schedule(
    session: AsyncSession,
    target_date: date,
    lessons: List[Tuple[int, str]]
) -> List[Schedule]:
    await clear_date_schedule(session, target_date)
    saved = []
    day_of_week = target_date.isoweekday()
    lesson_nums = {l_num for l_num, _ in lessons}

    for l_num, subj_name in lessons:
        subj = await get_or_create_subject(session, subj_name)
        item = await set_date_schedule_item(session, target_date, l_num, subj.id)
        saved.append(item)

    # Автоматически сохраняем постоянную внеурочку, если она не была явно переопределена в списке
    perm_lessons = await get_permanent_schedule_for_day(session, day_of_week)
    for p in perm_lessons:
        s_name = p.subject.name if p.subject else None
        if p.lesson_number not in lesson_nums and is_extracurricular_lesson(day_of_week, p.lesson_number, s_name):
            item = await set_date_schedule_item(
                session, target_date, p.lesson_number, p.subject_id,
                start_time=p.start_time, end_time=p.end_time
            )
            saved.append(item)

    return sorted(saved, key=lambda x: x.lesson_number)


async def save_bulk_permanent_schedule(
    session: AsyncSession,
    day_of_week: int,
    lessons: List[Tuple[int, str]]
) -> List[Schedule]:
    await freeze_past_schedules_for_weekday(session, day_of_week)
    await session.execute(
        delete(Schedule).where(Schedule.specific_date.is_(None), Schedule.day_of_week == day_of_week)
    )
    await session.commit()
    saved = []
    for l_num, subj_name in lessons:
        subj = await get_or_create_subject(session, subj_name)
        item = await set_schedule_item(
            session=session,
            day_of_week=day_of_week,
            lesson_number=l_num,
            subject_id=subj.id,
            specific_date=None
        )
        saved.append(item)
    return saved


# ----------------- SUBSTITUTIONS -----------------

async def get_substitutions_for_date(session: AsyncSession, target_date: date) -> List[Substitution]:
    result = await session.execute(
        select(Substitution)
        .options(
            joinedload(Substitution.old_subject),
            joinedload(Substitution.new_subject)
        )
        .where(Substitution.date == target_date)
        .order_by(Substitution.lesson_number)
    )
    return list(result.scalars().all())


async def create_substitution(
    session: AsyncSession,
    target_date: date,
    lesson_number: int,
    old_subject_id: Optional[int],
    new_subject_id: Optional[int],
    comment: Optional[str] = None,
    is_cancelled: bool = False
) -> Substitution:
    sub = Substitution(
        date=target_date,
        lesson_number=lesson_number,
        old_subject_id=old_subject_id,
        new_subject_id=new_subject_id,
        comment=comment,
        is_cancelled=is_cancelled
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub
