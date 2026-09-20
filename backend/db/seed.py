from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.crud import (
    get_all_subjects, create_subject,
    get_bell_schedule, set_bell_schedule_item,
    set_schedule_item
)

DEFAULT_SUBJECTS = [
    "Русский язык",
    "Литература",
    "Алгебра",
    "Геометрия",
    "Физика",
    "Химия",
    "Биология",
    "История",
    "Обществознание",
    "География",
    "Английский язык",
    "Информатика",
    "Физкультура",
    "ОБЖ",
]

# Exact official bell timings from class photo
DEFAULT_BELLS = [
    (1, "08:30", "09:10", 10),
    (2, "09:20", "10:00", 15),
    (3, "10:15", "10:55", 15),
    (4, "11:10", "11:50", 15),
    (5, "12:05", "12:45", 10),
    (6, "12:55", "13:35", 10),
    (7, "13:45", "14:25", 5),
    (8, "14:30", "15:10", 0),
]

DEFAULT_DUTY_GROUPS = [
    (0, "Группа 0", "Состав не назначен"),
    (1, "Группа 1", "Состав не назначен"),
    (2, "Группа 2", "Состав не назначен"),
    (3, "Группа 3", "Состав не назначен"),
    (4, "Группа 4", "Состав не назначен"),
    (5, "Группа 5", "Состав не назначен"),
]


async def seed_initial_data(session: AsyncSession):
    from datetime import date
    from backend.config import get_today
    today = get_today()

    # Check subjects
    existing_subjects = await get_all_subjects(session)
    if not existing_subjects:
        for name in DEFAULT_SUBJECTS:
            await create_subject(session, name=name)
    
    # Check bell schedule - ensure all 8 lessons exist
    existing_bells = await get_bell_schedule(session)
    if not existing_bells or len(existing_bells) < 8:
        for lesson_num, start_t, end_t, brk in DEFAULT_BELLS:
            await set_bell_schedule_item(session, lesson_num, start_t, end_t, brk)

    # Check duty groups
    from backend.db.crud import create_or_update_duty_group, get_duty_group_by_number
    from sqlalchemy import select, delete
    from backend.db.models import DutyGroup

    res = await session.execute(select(DutyGroup))
    existing_groups = {g.group_number: g for g in res.scalars().all()}

    for num, name, members in DEFAULT_DUTY_GROUPS:
        if num == 0 and today > date(2026, 9, 30):
            continue
        if num not in existing_groups:
            await create_or_update_duty_group(session, num, name, members)

    if today > date(2026, 9, 30) and 0 in existing_groups:
        await session.execute(delete(DutyGroup).where(DutyGroup.group_number == 0))
        await session.commit()

    # Clear any old placeholder names
    res_after = await session.execute(select(DutyGroup))
    for g in res_after.scalars().all():
        if any(fake in (g.members or "") for fake in ["Алексеев", "Дмитриев", "Иванов П.", "Никитин", "Смирнова"]):
            g.members = "Состав не назначен"
    await session.commit()

    # In September, ensure current_duty_group setting is empty so Group 0 is active by default
    from backend.db.crud import get_class_setting, set_class_setting
    if today.month == 9 and today.year == 2026:
        val = await get_class_setting(session, "current_duty_group")
        if val in ["1", "4"]:
            await set_class_setting(session, "current_duty_group", "")

    # Seed student birthdays for 11 «Б»
    from backend.db.crud.birthdays import seed_default_birthdays
    await seed_default_birthdays(session)

    # Seed Saturday Physics (09:00 - 11:00, separate lesson)
    from backend.db.crud.schedule import get_permanent_schedule_for_day, set_permanent_schedule_item
    sat_lessons = await get_permanent_schedule_for_day(session, 6)
    sat_physics = next((l for l in sat_lessons if l.subject and l.subject.name.strip().lower() == "физика"), None)
    if sat_physics:
        if sat_physics.start_time != "09:00" or sat_physics.end_time != "11:00":
            sat_physics.start_time = "09:00"
            sat_physics.end_time = "11:00"
            await session.commit()
    else:
        physics = next((s for s in existing_subjects if s.name.strip().lower() == "физика"), None)
        if not physics:
            for s in await get_all_subjects(session):
                if s.name.strip().lower() == "физика":
                    physics = s
                    break
        if physics:
            await set_permanent_schedule_item(
                session=session,
                day_of_week=6,
                lesson_number=1,
                subject_id=physics.id,
                start_time="09:00",
                end_time="11:00"
            )
