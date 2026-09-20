import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import date
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_birthdays.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_birthdays.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.models import Base, GroupChat
from backend.db.crud.birthdays import (
    seed_default_birthdays,
    get_all_birthdays,
    get_birthdays_for_date,
    get_upcoming_birthdays,
    DEFAULT_BIRTHDAYS
)
from backend.bot.services.birthdays import (
    format_birthday_message,
    check_and_send_birthday_greetings
)
from backend.bot.keyboards.main_menu import get_main_keyboard


async def run_birthdays_test_suite():
    print("=== [1/4] Testing Student Birthdays DB Initialization & Seeding ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Initial seed
        count = await seed_default_birthdays(session)
        assert count == 25, f"Expected 25 seeded birthdays, got {count}"
        
        # Idempotency test (calling again should not create duplicates)
        count_second = await seed_default_birthdays(session)
        assert count_second == 0, "Second seed should do nothing"

        all_students = await get_all_birthdays(session)
        assert len(all_students) == 25, f"Expected 25 students, got {len(all_students)}"
        print(f"[OK] 25 classmates successfully seeded into DB.")

        # Verify specific dates from user list
        gleb = [s for s in all_students if s.full_name == "Глеб"][0]
        assert gleb.birth_day == 16 and gleb.birth_month == 9

        isaykin = [s for s in all_students if s.full_name == "Исайкин"][0]
        assert isaykin.birth_day == 23 and isaykin.birth_month == 9

        darina = [s for s in all_students if s.full_name == "Дарина"][0]
        assert darina.birth_day == 17 and darina.birth_month == 6
        print("[OK] Exact student birth dates verified (Глеб 16.09, Исайкин 23.09, Дарина 17.06).")

    print("\n=== [2/4] Testing Date Queries & Upcoming Calculations ===")
    async with async_session_factory() as session:
        # Test query for September 16
        sept_16 = await get_birthdays_for_date(session, 16, 9)
        assert len(sept_16) == 1 and sept_16[0].full_name == "Глеб"

        # Test multi-birthday on July 10 (Арина & Полина)
        july_10 = await get_birthdays_for_date(session, 10, 7)
        assert len(july_10) == 2
        names_july = {s.full_name for s in july_10}
        assert "Арина" in names_july and "Полина" in names_july
        print("[OK] Same-day multiple birthdays verified (Арина & Полина 10.07).")

        # Test upcoming from reference date 2026-09-12
        ref_date = date(2026, 9, 12)
        upcoming = await get_upcoming_birthdays(session, ref_date, limit=4)
        assert len(upcoming) >= 3
        assert upcoming[0]["name"] == "Глеб" and upcoming[0]["days_left"] == 4
        assert upcoming[1]["name"] == "Исайкин" and upcoming[1]["days_left"] == 11
        assert upcoming[2]["name"] == "Макар" and upcoming[2]["days_left"] == 45
        print(f"[OK] Chronological upcoming calculation verified: 1. {upcoming[0]['name']} (через {upcoming[0]['days_left']} дн.), 2. {upcoming[1]['name']} (через {upcoming[1]['days_left']} дн.), 3. {upcoming[2]['name']}.")

    print("\n=== [3/4] Testing Birthday Congratulation Message & Topic Dispatch ===")
    async with async_session_factory() as session:
        gleb_list = await get_birthdays_for_date(session, 16, 9)
        msg_single = format_birthday_message(gleb_list, date(2026, 9, 16))
        assert "Глеб" in msg_single
        assert "С ДНЁМ РОЖДЕНИЯ" in msg_single
        assert "ЕГЭ" in msg_single
        assert "Сегодня наш класс поздравляет тебя" in msg_single
        print("[OK] Single celebrant greeting message format verified.")

        july_list = await get_birthdays_for_date(session, 10, 7)
        msg_multi = format_birthday_message(july_list, date(2026, 7, 10))
        assert "Арина" in msg_multi and "Полина" in msg_multi
        assert "От всего нашего класса желаем вам" in msg_multi
        print("[OK] Multi celebrant greeting message format verified.")

        # Test group dispatch with topic_announcements_id
        group = GroupChat(
            chat_id=-1001234567890,
            title="11 «Б» Классный Чат",
            chat_type="supergroup",
            role="approved",
            notifications_enabled=True,
            topic_announcements_id=777
        )
        session.add(group)
        await session.commit()

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        # Run birthday check
        from unittest.mock import patch
        with patch("backend.bot.services.birthdays.get_today", return_value=date(2026, 9, 16)):
            sent = await check_and_send_birthday_greetings(mock_bot, force=True)
            assert sent == 1
            mock_bot.send_message.assert_called_once()
            call_kwargs = mock_bot.send_message.call_args.kwargs
            assert call_kwargs["chat_id"] == -1001234567890
            assert call_kwargs["message_thread_id"] == 777
            assert "Глеб" in call_kwargs["text"]
            print("[OK] Dispatched birthday congratulations to group chat in topic_announcements_id=777.")

            # Test idempotency (calling again on same date without force should skip)
            sent_duplicate = await check_and_send_birthday_greetings(mock_bot, force=False)
            assert sent_duplicate == 0, "Duplicate greetings should be blocked on same date"
            print("[OK] Duplicate check protection on same date verified.")

        # Test Isaykin special 3-message notification on September 23
        mock_bot_isaykin = AsyncMock()
        mock_bot_isaykin.send_message = AsyncMock()
        with patch("backend.bot.services.birthdays.get_today", return_value=date(2026, 9, 23)):
            sent_isaykin = await check_and_send_birthday_greetings(mock_bot_isaykin, force=True)
            assert sent_isaykin == 3, f"Expected 3 messages for Isaykin, got {sent_isaykin}"
            assert mock_bot_isaykin.send_message.call_count == 3
            for call in mock_bot_isaykin.send_message.call_args_list:
                msg_txt = call.kwargs["text"]
                assert "Исайкин с днем рождения!!!!" in msg_txt
                assert "🎂" in msg_txt and ("🎆" in msg_txt or "🎇" in msg_txt)
            print("[OK] Isaykin special 3-message greeting with cakes & fireworks verified.")

    print("\n=== [4/4] Testing Main Menu Keyboard Integration ===")
    kb = get_main_keyboard(is_admin=True)
    all_buttons = [b.text for row in kb.keyboard for b in row]
    assert "🎂 Дни рождения" in all_buttons, "Button '🎂 Дни рождения' must be present in main menu keyboard"
    print("[OK] '🎂 Дни рождения' button verified in main keyboard.")

    print("\n" + "=" * 60)
    print(">>> ALL BIRTHDAY TESTS PASSED FLAWLESSLY! ZERO ERRORS! <<<")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_birthdays_test_suite())
