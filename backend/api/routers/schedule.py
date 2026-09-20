from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.crud import (
    get_schedule_for_date, get_substitutions_for_date,
    get_bell_schedule_for_date, get_full_week_schedule,
    get_bell_schedule
)
from backend.config import get_today

router = APIRouter(tags=["schedule"])


@router.get("/schedule")
async def get_schedule(
    target_date: Optional[str] = Query(None, description="ISO format date YYYY-MM-DD"),
    session: AsyncSession = Depends(get_db_session)
):
    if target_date:
        query_date = date.fromisoformat(target_date)
    else:
        query_date = get_today()

    day_of_week = query_date.isoweekday()
    schedules = await get_schedule_for_date(session, query_date)
    subs = await get_substitutions_for_date(session, query_date)

    bells = {b.lesson_number: b for b in await get_bell_schedule_for_date(session, query_date)}

    # Merge schedule with substitutions and bells
    sub_map = {s.lesson_number: s for s in subs}
    lessons = []

    max_lesson = max(
        [s.lesson_number for s in schedules] + [s.lesson_number for s in subs] or [0]
    )

    sched_map = {s.lesson_number: s for s in schedules}

    for num in range(1, max_lesson + 1):
        bell = bells.get(num)
        base = sched_map.get(num)
        sub = sub_map.get(num)

        start_t = base.start_time if base and base.start_time else (bell.start_time if bell else "")
        end_t = base.end_time if base and base.end_time else (bell.end_time if bell else "")

        lesson_item = {
            "lesson_number": num,
            "start_time": start_t,
            "end_time": end_t,
            "is_substitution": False,
            "is_cancelled": False,
            "subject_name": "",
            "comment": ""
        }

        if sub:
            if sub.is_cancelled:
                continue
            lesson_item["is_substitution"] = True
            lesson_item["is_cancelled"] = False
            lesson_item["comment"] = sub.comment or ""
            lesson_item["subject_name"] = sub.new_subject.name if sub.new_subject else (base.subject.name if base else "Урок")
            lessons.append(lesson_item)
        elif base:
            lesson_item["subject_name"] = base.subject.name if base.subject else "Урок"
            lessons.append(lesson_item)

    from backend.bot.services.academic_calendar import get_day_special_status
    day_status, status_text = get_day_special_status(query_date)

    return {
        "date": query_date.isoformat(),
        "day_of_week": day_of_week,
        "class_name": "11 «Б»",
        "day_status": day_status,
        "status_text": status_text,
        "lessons": lessons
    }


@router.get("/schedule/week")
async def get_week_schedule(session: AsyncSession = Depends(get_db_session)):
    week_map = await get_full_week_schedule(session)
    bells = {b.lesson_number: b for b in await get_bell_schedule(session)}

    result = {}
    for day_num, items in week_map.items():
        lessons = []
        for it in items:
            bell = bells.get(it.lesson_number)
            lessons.append({
                "lesson_number": it.lesson_number,
                "start_time": it.start_time or (bell.start_time if bell else ""),
                "end_time": it.end_time or (bell.end_time if bell else ""),
                "subject_name": it.subject.name
            })
        result[day_num] = lessons

    return result
