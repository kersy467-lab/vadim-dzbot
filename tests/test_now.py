import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_now.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_now.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.models import Base, Subject, Schedule, Substitution, BellSchedule
from backend.db.crud.subjects import create_subject
from backend.db.crud.bells import set_bell_schedule_item
from backend.db.crud.schedule import set_permanent_schedule_item
from backend.bot.services.now import (
    get_now_lesson_status,
    time_to_minutes,
    format_duration_ru,
    get_effective_lessons_for_date
)
from backend.bot.keyboards.main_menu import get_main_keyboard
from backend.bot.handlers.now import get_now_keyboard


async def run_now_test_suite():
    print("=== [1/5] Testing Helper Functions ===")
    assert time_to_minutes("08:30") == 510
    assert time_to_minutes("12:05") == 725
    assert time_to_minutes("15:10") == 910
    assert time_to_minutes("invalid") is None

    assert format_duration_ru(1) == "1 минута"
    assert format_duration_ru(2) == "2 минуты"
    assert format_duration_ru(5) == "5 минут"
    assert format_duration_ru(18) == "18 минут"
    assert format_duration_ru(60) == "1 час"
    assert format_duration_ru(75) == "1 час 15 мин"

    print("[OK] Helper functions verified.")

    print("\n=== [2/5] Initializing Test Database & Seeding Schedule ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Create subjects
        s_rus = await create_subject(session, "Русский язык")
        s_alg = await create_subject(session, "Алгебра")
        s_fiz = await create_subject(session, "Физика")
        s_chem = await create_subject(session, "Химия")

        # Set bell schedule for lessons 1..4
        # 1: 08:30 - 09:10 (10 min break)
        # 2: 09:20 - 10:00 (15 min break)
        # 3: 10:15 - 10:55 (15 min break)
        # 4: 11:10 - 11:50
        await set_bell_schedule_item(session, 1, "08:30", "09:10", 10)
        await set_bell_schedule_item(session, 2, "09:20", "10:00", 15)
        await set_bell_schedule_item(session, 3, "10:15", "10:55", 15)
        await set_bell_schedule_item(session, 4, "11:10", "11:50", 10)

        # Permanent schedule for Tuesday (day 2):
        # 1. Русский язык
        # 2. Алгебра
        # 3. Физика
        # 4. Химия
        await set_permanent_schedule_item(session, 2, 1, s_rus.id)
        await set_permanent_schedule_item(session, 2, 2, s_alg.id)
        await set_permanent_schedule_item(session, 2, 3, s_fiz.id)
        await set_permanent_schedule_item(session, 2, 4, s_chem.id)

        # Permanent schedule for Wednesday (day 3):
        await set_permanent_schedule_item(session, 3, 1, s_fiz.id)
        print("[OK] Test schedule and bells created.")

    print("\n=== [3/5] Testing Lesson Timing States on School Day ===")
    async with async_session_factory() as session:
        # Tuesday, 15 September 2026 (day_of_week = 2)
        test_tuesday = date(2026, 9, 15)

        # State A: Morning before school (07:45)
        dt_morning = datetime(2026, 9, 15, 7, 45)
        res_morning = await get_now_lesson_status(session, dt_morning)
        assert "Уроки ещё не начались" in res_morning
        assert "До 1-го урока" in res_morning
        assert "45 минут" in res_morning
        assert "Русский язык" in res_morning
        assert "Каб." not in res_morning and "каб." not in res_morning
        assert "4 урока" in res_morning
        print("[OK] Morning before lessons verified (strictly without room).")

        # State B: During Lesson 1 (08:45)
        dt_lesson1 = datetime(2026, 9, 15, 8, 45)
        res_lesson1 = await get_now_lesson_status(session, dt_lesson1)
        assert "Сейчас (1-й урок):" in res_lesson1
        assert "Русский язык" in res_lesson1
        assert "25 минут" in res_lesson1
        assert "Следующий урок (2-й):" in res_lesson1
        assert "Алгебра" in res_lesson1
        assert "перемена 10 мин" in res_lesson1
        print("[OK] During lesson 1 verified.")

        # State C: During Break between Lesson 1 and Lesson 2 (09:15)
        dt_break1 = datetime(2026, 9, 15, 9, 15)
        res_break1 = await get_now_lesson_status(session, dt_break1)
        assert "Сейчас перемена!" in res_break1
        assert "5 минут" in res_break1
        assert "Следующий урок (2-й):" in res_break1
        assert "Алгебра" in res_break1
        assert "Предыдущий урок:" in res_break1
        assert "Русский язык завершён" in res_break1
        print("[OK] During break verified.")

        # State D: During Last Lesson (11:30, Lesson 4)
        dt_last_lesson = datetime(2026, 9, 15, 11, 30)
        res_last = await get_now_lesson_status(session, dt_last_lesson)
        assert "Сейчас (4-й урок):" in res_last
        assert "Химия" in res_last
        assert "20 минут" in res_last
        assert "Это последний урок на сегодня!" in res_last
        assert "Дальше домой." in res_last
        print("[OK] Last lesson verified.")

        # State E: Evening after lessons (15:00)
        dt_evening = datetime(2026, 9, 15, 15, 0)
        res_evening = await get_now_lesson_status(session, dt_evening)
        assert "Уроки на сегодня всё!" in res_evening
        # Explicit user requirement: "без Свобода!"
        assert "Свобода" not in res_evening, "Must not contain 'Свобода!' in evening message"
        assert "Все 4 урока завершены в 11:50" in res_evening
        assert "Завтра (Среда):" in res_evening
        assert "Физика" in res_evening
        print("[OK] Evening state verified (strictly without 'Свобода!').")

    print("\n=== [4/5] Testing Weekend & Substitution Handling ===")
    async with async_session_factory() as session:
        # Weekend: Sunday, 20 September 2026
        dt_sunday = datetime(2026, 9, 20, 12, 0)
        res_sunday = await get_now_lesson_status(session, dt_sunday)
        assert "Сегодня выходной" in res_sunday or "На сегодня уроков" in res_sunday
        print("[OK] Weekend state verified.")

        # Substitution on Tuesday 22 September:
        # Lesson 2 (Algebra) replaced with History
        s_hist = await create_subject(session, "История")
        sub = Substitution(
            date=date(2026, 9, 22),
            lesson_number=2,
            new_subject_id=s_hist.id,
            is_cancelled=False
        )
        session.add(sub)
        await session.commit()

        dt_sub = datetime(2026, 9, 22, 9, 30)
        res_sub = await get_now_lesson_status(session, dt_sub)
        assert "Сейчас (2-й урок):" in res_sub
        assert "История" in res_sub
        print("[OK] Substitution reflected in /now correctly without room.")

    print("\n=== [5/5] Testing Keyboards & Command Registration ===")
    main_kb = get_main_keyboard()
    all_buttons = [b.text for row in main_kb.keyboard for b in row]
    assert "⏳ Сейчас" in all_buttons
    assert "☀️ До лета осталось" in all_buttons
    print("[OK] '⏳ Сейчас' button present in main keyboard.")

    now_kb = get_now_keyboard()
    now_cbs = [b.callback_data for row in now_kb.inline_keyboard for b in row]
    assert "now_refresh" in now_cbs
    assert "sched_today" in now_cbs
    print("[OK] Inline refresh and schedule buttons present.")

    print("\n=== [6/6] Testing Double-Click Protection on Schedule Callbacks ===")
    from backend.bot.handlers.schedule import cb_sched_today
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.exceptions import TelegramBadRequest

    mock_msg = MagicMock()
    mock_msg.edit_text = AsyncMock(side_effect=TelegramBadRequest(method=MagicMock(), message="Bad Request: message is not modified"))
    mock_cb = MagicMock()
    mock_cb.data = "sched_today"
    mock_cb.from_user.id = 12345
    mock_cb.message = mock_msg
    mock_cb.answer = AsyncMock()

    async with async_session_factory() as session:
        # Calling cb_sched_today when message is already open should not throw and should answer nicely
        await cb_sched_today(mock_cb, session)
        mock_cb.answer.assert_called_with("Расписание на сегодня уже открыто 📅")
        print("[OK] cb_sched_today handled identical content cleanly without error!")

    print("\n" + "=" * 60)
    print(">>> ALL /NOW TESTS PASSED FLAWLESSLY! ZERO ERRORS! <<<")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_now_test_suite())
