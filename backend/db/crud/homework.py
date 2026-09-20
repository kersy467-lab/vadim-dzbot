from datetime import date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.db.models import Homework, UserHomeworkStatus, Deadline, Announcement, Subject


async def create_homework(
    session: AsyncSession,
    subject_id: int,
    due_date: date,
    description: str,
    title: Optional[str] = None,
    attachments: Optional[list] = None,
    created_by: Optional[int] = None,
    assigned_date: Optional[date] = None
) -> Homework:
    hw = Homework(
        subject_id=subject_id,
        due_date=due_date,
        assigned_date=assigned_date or date.today(),
        title=title,
        description=description,
        attachments=attachments or [],
        created_by=created_by
    )
    session.add(hw)
    await session.commit()
    await session.refresh(hw)
    return hw


async def get_homework_for_date(session: AsyncSession, target_date: date) -> List[Homework]:
    result = await session.execute(
        select(Homework)
        .options(joinedload(Homework.subject))
        .where(Homework.due_date == target_date)
        .order_by(Homework.created_at.desc())
    )
    return list(result.scalars().all())


async def get_homework_by_subject(
    session: AsyncSession,
    subject_id: int,
    limit: int = 10,
    from_date: Optional[date] = None
) -> List[Homework]:
    from backend.config import get_today
    if from_date is None:
        from_date = get_today()
    result = await session.execute(
        select(Homework)
        .options(joinedload(Homework.subject))
        .where(Homework.subject_id == subject_id, Homework.due_date >= from_date)
        .order_by(Homework.due_date.asc())
        .limit(limit)
    )
    items = list(result.scalars().all())
    return [h for h in items if h.due_date >= from_date]


async def get_homework_by_id(session: AsyncSession, hw_id: int) -> Optional[Homework]:
    result = await session.execute(
        select(Homework)
        .options(joinedload(Homework.subject))
        .where(Homework.id == hw_id)
    )
    return result.scalar_one_or_none()


async def get_user_homework_status(session: AsyncSession, user_id: int, hw_id: int) -> Optional[UserHomeworkStatus]:
    result = await session.execute(
        select(UserHomeworkStatus).where(
            UserHomeworkStatus.user_id == user_id,
            UserHomeworkStatus.homework_id == hw_id
        )
    )
    return result.scalar_one_or_none()


async def toggle_homework_completion(session: AsyncSession, user_id: int, hw_id: int) -> bool:
    status = await get_user_homework_status(session, user_id, hw_id)
    if status and status.is_completed:
        # Галочка снята: удаляем запись из БД, чтобы не хранить пустые статусы
        await session.delete(status)
        await session.commit()
        return False
    elif status and not status.is_completed:
        status.is_completed = True
        await session.commit()
        return True
    else:
        status = UserHomeworkStatus(user_id=user_id, homework_id=hw_id, is_completed=True)
        session.add(status)
        await session.commit()
        return True


async def cleanup_past_homework_statuses(session: AsyncSession, before_date: Optional[date] = None) -> int:
    """
    Автоматически удаляет ненужные записи чеклиста из базы данных:
    1. Все записи чеклиста для ДЗ, срок сдачи которых уже прошёл (due_date < today).
    2. Все записи со статусом is_completed = False (снятые галочки).
    Возвращает суммарное количество удалённых устаревших записей.
    """
    if before_date is None:
        from backend.config import get_today
        before_date = get_today()

    # 1. Удаляем статусы для прошедших заданий
    stmt_past = delete(UserHomeworkStatus).where(
        UserHomeworkStatus.homework_id.in_(
            select(Homework.id).where(Homework.due_date < before_date)
        )
    )
    res_past = await session.execute(stmt_past)

    # 2. Удаляем любые оставшиеся статусы со значением False
    stmt_false = delete(UserHomeworkStatus).where(
        UserHomeworkStatus.is_completed.is_(False)
    )
    res_false = await session.execute(stmt_false)

    await session.commit()
    total_deleted = (res_past.rowcount or 0) + (res_false.rowcount or 0)
    return total_deleted


async def delete_homework(session: AsyncSession, hw_id: int) -> bool:
    """Удаляет домашнее задание и все связанные статусы выполнения"""
    await session.execute(delete(UserHomeworkStatus).where(UserHomeworkStatus.homework_id == hw_id))
    result = await session.execute(delete(Homework).where(Homework.id == hw_id))
    await session.commit()
    return (result.rowcount or 0) > 0


async def get_recent_active_homeworks(session: AsyncSession, limit: int = 15) -> List[Homework]:
    """Возвращает список актуальных ДЗ (начиная с сегодняшнего дня) для управления администратором"""
    from backend.config import get_today
    today = get_today()
    result = await session.execute(
        select(Homework)
        .options(joinedload(Homework.subject))
        .where(Homework.due_date >= today)
        .order_by(Homework.due_date.asc(), Homework.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_all_upcoming_homeworks(session: AsyncSession, from_date: Optional[date] = None) -> List[Homework]:
    """Возвращает все домашние задания, начиная с from_date (по умолчанию сегодня) и на любые будущие даты"""
    from backend.config import get_today
    if from_date is None:
        from_date = get_today()
    result = await session.execute(
        select(Homework)
        .options(joinedload(Homework.subject))
        .where(Homework.due_date >= from_date)
        .order_by(Homework.due_date.asc(), Homework.created_at.desc())
    )
    return list(result.scalars().all())


# ----------------- DEADLINES -----------------

async def get_upcoming_deadlines(session: AsyncSession, from_date: Optional[date] = None) -> List[Deadline]:
    if from_date is None:
        from_date = date.today()
    result = await session.execute(
        select(Deadline)
        .options(joinedload(Deadline.subject))
        .where(Deadline.due_date >= from_date)
        .order_by(Deadline.due_date.asc())
    )
    return list(result.scalars().all())


async def create_deadline(
    session: AsyncSession,
    title: str,
    due_date: date,
    subject_id: Optional[int] = None,
    description: Optional[str] = None,
    created_by: Optional[int] = None
) -> Deadline:
    dl = Deadline(
        title=title,
        due_date=due_date,
        subject_id=subject_id,
        description=description,
        created_by=created_by
    )
    session.add(dl)
    await session.commit()
    await session.refresh(dl)
    return dl


async def delete_deadline(session: AsyncSession, deadline_id: int) -> bool:
    result = await session.execute(select(Deadline).where(Deadline.id == deadline_id))
    dl = result.scalar_one_or_none()
    if dl:
        await session.delete(dl)
        await session.commit()
        return True
    return False


# ----------------- ANNOUNCEMENTS -----------------

async def create_announcement(
    session: AsyncSession,
    text: str,
    attachments: Optional[list] = None,
    created_by: Optional[int] = None
) -> Announcement:
    ann = Announcement(
        text=text,
        attachments=attachments or [],
        created_by=created_by
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    return ann


async def get_recent_announcements(session: AsyncSession, limit: int = 5) -> List[Announcement]:
    result = await session.execute(
        select(Announcement).order_by(Announcement.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


# ----------------- SMART HOMEWORK SCHEDULING & AUTO-SHIFT -----------------

async def is_subject_scheduled_on_date(session: AsyncSession, subject_id: int, target_date: date) -> bool:
    """
    Проверяет, есть ли урок по subject_id в расписании на указанную дату
    (с учетом индивидуального расписания даты, постоянного расписания и замен).
    """
    if target_date <= date(2026, 9, 1):
        return False

    # Субботняя физика — отдельное занятие, ДЗ по физике на субботу не ставится
    if target_date.isoweekday() == 6:
        subj = await session.get(Subject, subject_id)
        if subj and subj.name.strip().lower() == "физика":
            return False

    from backend.db.crud.schedule import get_substitutions_for_date, get_schedule_for_date

    subs = await get_substitutions_for_date(session, target_date)
    sub_map = {s.lesson_number: s for s in subs}

    schedules = await get_schedule_for_date(session, target_date)
    sched_map = {s.lesson_number: s for s in schedules}

    all_lesson_nums = set(sched_map.keys()) | set(sub_map.keys())
    for num in all_lesson_nums:
        sub = sub_map.get(num)
        base = sched_map.get(num)

        if sub:
            if not sub.is_cancelled and sub.new_subject_id == subject_id:
                return True
        elif base:
            if base.subject_id == subject_id:
                return True

    return False


async def find_upcoming_dates_for_subject(
    session: AsyncSession,
    subject_id: int,
    from_date: Optional[date] = None,
    limit: int = 4,
    max_days_forward: int = 35
) -> List[date]:
    """
    Находит ближайшие даты, в которые данный предмет стоит в расписании,
    начиная с from_date (по умолчанию завтра).
    """
    from backend.config import get_today
    start_d = from_date or (get_today() + timedelta(days=1))
    results = []

    for offset in range(max_days_forward):
        cur_d = start_d + timedelta(days=offset)
        if await is_subject_scheduled_on_date(session, subject_id, cur_d):
            results.append(cur_d)
            if len(results) >= limit:
                break

    return results


async def auto_shift_active_homeworks(
    session: AsyncSession,
    affected_subject_id: Optional[int] = None
) -> List[Tuple[Homework, date, date]]:
    """
    Автоматически сдвигает сроки сдачи активных домашних заданий:
    - Если в расписании появился этот урок раньше (или урок перенесся/отменился),
      срок сдачи сдвигается на правильную актуальную дату следующего урока.
    - Прошедшие/сданные ДЗ (due_date < today) закрыты и НИКОГДА не меняются.
    Возвращает список кортежей (hw, old_due_date, new_due_date).
    """
    from backend.config import get_today
    today = get_today()

    query = select(Homework).where(Homework.due_date >= today)
    if affected_subject_id is not None:
        query = query.where(Homework.subject_id == affected_subject_id)

    res = await session.execute(query)
    active_hws = res.scalars().all()

    shifted = []
    for hw in active_hws:
        assigned_d = hw.assigned_date or hw.created_at.date()
        earliest_possible = max(assigned_d + timedelta(days=1), today)

        current_due_is_valid = await is_subject_scheduled_on_date(session, hw.subject_id, hw.due_date)

        upcoming = await find_upcoming_dates_for_subject(
            session, hw.subject_id, from_date=earliest_possible, limit=1
        )

        if not upcoming:
            continue

        first_avail = upcoming[0]

        if first_avail < hw.due_date or not current_due_is_valid:
            if first_avail != hw.due_date:
                old_d = hw.due_date
                hw.due_date = first_avail
                shifted.append((hw, old_d, first_avail))

    if shifted:
        await session.commit()

    return shifted
