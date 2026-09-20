import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import date, datetime, timedelta

# Ensure backend can be imported and uses isolated SQLite for local tests
sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_saturday_physics.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_saturday_physics.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.models import Base, Subject, Schedule
from backend.db.seed import seed_initial_data
from backend.db.crud import (
    get_all_subjects, get_permanent_schedule_for_day, get_schedule_for_date,
    set_permanent_schedule_item, is_subject_scheduled_on_date,
    find_upcoming_dates_for_subject, auto_shift_active_homeworks,
    create_homework, create_user, create_or_update_group_chat
)
from backend.bot.handlers.schedule import format_day_schedule
from backend.bot.handlers.admin.homework.helpers import (
    is_saturday_physics, get_upcoming_or_fallback_dates
)
from backend.bot.services.now import get_effective_lessons_for_date, get_now_lesson_status
from backend.bot.services.notifier import send_evening_digest


async def test_saturday_physics_feature():
    print("--- [1/5] Testing Database Seeding and Saturday Physics Schedule ---")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await seed_initial_data(session)

        # Verify Saturday schedule seeded
        sat_lessons = await get_permanent_schedule_for_day(session, 6)
        assert len(sat_lessons) == 1, f"Expected 1 lesson on Saturday, got {len(sat_lessons)}"
        sat_item = sat_lessons[0]
        assert sat_item.lesson_number == 1
        assert sat_item.subject.name == "Физика"
        assert sat_item.start_time == "09:00"
        assert not hasattr(sat_item, "room"), "Schedule model must not have room attribute"
        print("  [OK] Saturday Physics (09:00 - 11:00) seeded successfully without room.")

        # Test schedule formatting on Saturday
        # Saturday: 2026-09-19
        sat_date = date(2026, 9, 19)
        assert sat_date.isoweekday() == 6
        formatted = await format_day_schedule(session, sat_date)
        assert "Физика" in formatted
        assert "09:00-11:00" in formatted
        print("  [OK] Saturday schedule formatting contains '09:00-11:00' and 'Физика'.")

        physics_id = sat_item.subject_id

        # Also add weekday physics on Tuesday (Day 2) and Thursday (Day 4) to test realistic schedule
        await set_permanent_schedule_item(session, day_of_week=2, lesson_number=3, subject_id=physics_id)
        await set_permanent_schedule_item(session, day_of_week=4, lesson_number=2, subject_id=physics_id)

    print("\n--- [2/4] Testing Homework Date Exclusion for Physics on Saturday ---")
    async with async_session_factory() as session:
        # 1. is_subject_scheduled_on_date for Saturday
        assert await is_subject_scheduled_on_date(session, physics_id, sat_date) is False, \
            "Saturday Physics must NOT be considered scheduled for homework!"
        print("  [OK] is_subject_scheduled_on_date returns False for Saturday Physics.")

        # 2. find_upcoming_dates_for_subject starting from Friday before Saturday (e.g. 2026-09-18)
        # Saturday is 2026-09-19. Next lessons should be Tuesday 2026-09-22, Thursday 2026-09-24.
        upcoming = await find_upcoming_dates_for_subject(session, physics_id, from_date=date(2026, 9, 19), limit=3)
        assert sat_date not in upcoming, f"Saturday {sat_date} must NOT be in upcoming dates: {upcoming}"
        assert date(2026, 9, 22) in upcoming, f"Expected Tuesday 2026-09-22 in upcoming, got {upcoming}"
        print(f"  [OK] find_upcoming_dates_for_subject skipped Saturday: {upcoming}")

        # 3. get_upcoming_or_fallback_dates
        fallback_dates, is_sched = await get_upcoming_or_fallback_dates(session, physics_id, from_date=date(2026, 9, 19), limit=4)
        assert is_sched is True
        assert sat_date not in fallback_dates, f"Saturday must NEVER be in suggested dates: {fallback_dates}"
        print(f"  [OK] get_upcoming_or_fallback_dates never suggests Saturday: {fallback_dates}")

        # 4. is_saturday_physics helper
        assert is_saturday_physics("Физика", sat_date) is True
        assert is_saturday_physics("Физика", date(2026, 9, 22)) is False # Tuesday
        assert is_saturday_physics("Алгебра", sat_date) is False
        print("  [OK] is_saturday_physics helper validated.")

    print("\n--- [3/4] Testing Auto-Shift Homework Protection ---")
    async with async_session_factory() as session:
        # Create active physics homework assigned on Thursday 2026-09-17, due Tuesday 2026-09-22
        hw = await create_homework(
            session=session,
            subject_id=physics_id,
            due_date=date(2026, 9, 22),
            assigned_date=date(2026, 9, 17),
            description="Задачи 10-15 по динамике"
        )
        # Run auto_shift_active_homeworks
        shifted = await auto_shift_active_homeworks(session, affected_subject_id=physics_id)
        # It should NOT shift to Saturday 2026-09-19
        for h, old_d, new_d in shifted:
            assert new_d != sat_date, f"Auto-shift shifted homework to Saturday {sat_date}!"
        assert hw.due_date != sat_date
        print("  [OK] auto_shift_active_homeworks strictly preserves exclusion of Saturday.")

    print("\n--- [4/4] Testing /now status on Saturday ---")
    async with async_session_factory() as session:
        slots = await get_effective_lessons_for_date(session, sat_date)
        assert len(slots) == 1, f"Expected 1 slot on Saturday, got {len(slots)}"
        slot = slots[0]
        assert slot.subject_name == "Физика"
        assert slot.start_time == "09:00"
        assert slot.end_time == "11:00"
        assert slot.start_minutes == 540
        assert slot.end_minutes == 660

        # Test at 09:30 (during lesson)
        status_during = await get_now_lesson_status(session, now_dt=datetime(2026, 9, 19, 9, 30))
        assert "Физика" in status_during
        assert "До конца урока" in status_during
        assert "11:00" in status_during
        assert "Каб." not in status_during and "каб." not in status_during
        print("  [OK] /now during Saturday Physics shows ongoing lesson until 11:00 without room.")

        # Test at 08:30 (before lesson)
        status_before = await get_now_lesson_status(session, now_dt=datetime(2026, 9, 19, 8, 30))
        assert "До 1-го урока" in status_before
        assert "09:00" in status_before
        assert "Каб." not in status_before and "каб." not in status_before
        print("  [OK] /now before Saturday Physics shows countdown to 09:00 without room.")

        # Test at 12:00 (after lesson)
        status_after = await get_now_lesson_status(session, now_dt=datetime(2026, 9, 19, 12, 0))
        assert "Уроки на сегодня всё!" in status_after
        print("  [OK] /now after Saturday Physics shows lessons ended.")

    print("\n--- [5/5] Testing Friday Evening Digest for Saturday ---")
    async with async_session_factory() as session:
        # Create student and approved group
        user_test = await create_user(session, tg_id=999888, full_name="Тестовый Ученик", role="student")
        await create_or_update_group_chat(session, chat_id=-100999888, title="11 Б Чат", chat_type="supergroup", role="approved")

        # Create homework for next week Tuesday
        await create_homework(
            session=session,
            subject_id=physics_id,
            due_date=date(2026, 9, 22),
            assigned_date=date(2026, 9, 18),
            description="Подготовка к контрольной"
        )

        class MockDigestBot:
            def __init__(self):
                self.messages = {}
            async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None):
                self.messages.setdefault(chat_id, []).append(text)

        digest_bot = MockDigestBot()

        # Send evening digest targeting Saturday 2026-09-19
        sent = await send_evening_digest(digest_bot, target_date=sat_date)
        assert sent > 0, "Expected digest to be sent for Saturday with lessons"

        # Verify group message
        assert -100999888 in digest_bot.messages, "Group must receive Saturday digest"
        group_msg = digest_bot.messages[-100999888][0]
        assert "Физика" in group_msg
        assert "09:00-11:00" in group_msg
        assert "Каб." not in group_msg and "каб." not in group_msg
        # Strictly no homework blocks in Saturday notification ("только в расписании")
        assert "Домашнее задание" not in group_msg
        assert "Подготовка к контрольной" not in group_msg
        print("  [OK] Group message contains Saturday schedule and NO homework block.")

        # Verify student PM message
        assert 999888 in digest_bot.messages, "Student must receive Saturday digest in PM"
        user_msg = digest_bot.messages[999888][0]
        assert "Физика" in user_msg
        assert "09:00-11:00" in user_msg
        assert "Каб." not in user_msg and "каб." not in user_msg
        # Strictly no homework checklist in student PM for Saturday
        assert "Домашнее задание" not in user_msg
        assert "Подготовка к контрольной" not in user_msg
        assert "[ ]" not in user_msg and "[x]" not in user_msg
        print("  [OK] Student PM message contains Saturday schedule and NO homework checklist.")

    print("\n=== ALL SATURDAY PHYSICS TESTS PASSED! ZERO ERRORS! ===")


if __name__ == "__main__":
    asyncio.run(test_saturday_physics_feature())
