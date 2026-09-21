from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.db.models import UserCustomSchedule


async def get_user_custom_schedules(
    session: AsyncSession,
    user_tg_id: int
) -> List[UserCustomSchedule]:
    """Возвращает персональное расписание пользователя на все дни недели (1..7)."""
    result = await session.execute(
        select(UserCustomSchedule)
        .where(UserCustomSchedule.user_tg_id == user_tg_id)
        .order_by(UserCustomSchedule.day_of_week)
    )
    return list(result.scalars().all())


async def save_user_custom_schedules(
    session: AsyncSession,
    user_tg_id: int,
    user_id: Optional[int],
    days_data: Dict[int, Dict[str, Any]]
) -> List[UserCustomSchedule]:
    """
    Сохраняет или перезаписывает персональное расписание пользователя на всю неделю.
    days_data: словарь {day_num (1..7): {
        'is_active': bool,
        'content_type': Optional[str],
        'file_id': Optional[str],
        'text_content': Optional[str],
        'notification_time': Optional[str]
    }}
    """
    # Удаляем старые записи пользователя
    await session.execute(
        delete(UserCustomSchedule).where(UserCustomSchedule.user_tg_id == user_tg_id)
    )

    new_records: List[UserCustomSchedule] = []
    now = datetime.utcnow()

    for day_num in range(1, 8):
        day_info = days_data.get(day_num, {})
        is_active = bool(day_info.get("is_active", False))
        record = UserCustomSchedule(
            user_id=user_id,
            user_tg_id=user_tg_id,
            day_of_week=day_num,
            is_active=is_active,
            content_type=day_info.get("content_type") if is_active else None,
            file_id=day_info.get("file_id") if is_active else None,
            text_content=day_info.get("text_content") if is_active else None,
            notification_time=day_info.get("notification_time") if is_active else None,
            last_sent_date=None,
            created_at=now,
            updated_at=now
        )
        session.add(record)
        new_records.append(record)

    await session.commit()
    for rec in new_records:
        await session.refresh(rec)
    return new_records


async def get_due_custom_schedules(
    session: AsyncSession,
    day_of_week: int,
    current_time: str,
    current_date: date
) -> List[UserCustomSchedule]:
    """
    Выбирает активные расписания для текущего дня недели и времени,
    которые еще не были отправлены сегодня.
    """
    query = (
        select(UserCustomSchedule)
        .where(
            UserCustomSchedule.is_active == True,
            UserCustomSchedule.day_of_week == day_of_week,
            UserCustomSchedule.notification_time == current_time,
            (UserCustomSchedule.last_sent_date == None) | (UserCustomSchedule.last_sent_date != current_date)
        )
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def mark_schedule_sent(
    session: AsyncSession,
    schedule_id: int,
    sent_date: date
) -> None:
    """Отмечает дату последней отправки расписания."""
    result = await session.execute(
        select(UserCustomSchedule).where(UserCustomSchedule.id == schedule_id)
    )
    rec = result.scalar_one_or_none()
    if rec:
        rec.last_sent_date = sent_date
        rec.updated_at = datetime.utcnow()
        await session.commit()


async def delete_user_custom_schedules(
    session: AsyncSession,
    user_tg_id: int
) -> int:
    """Удаляет все сохраненные пользовательские расписания."""
    result = await session.execute(
        delete(UserCustomSchedule).where(UserCustomSchedule.user_tg_id == user_tg_id)
    )
    await session.commit()
    return result.rowcount or 0
