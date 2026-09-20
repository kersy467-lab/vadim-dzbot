import asyncio
import os
import sys
from datetime import date
from sqlalchemy import select, delete

# Setup test environment
sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_bell_wizard.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_bell_wizard.db"

from backend.db.session import async_session_factory, engine
from backend.db.models import Base, BellSchedule
from backend.db.crud import get_bell_schedule, set_bell_schedule_item, get_bell_schedule_for_date
from backend.bot.handlers.admin.bells.wizard_breaks import (
    _generate_bells_list,
    _init_default_breaks,
)


def test_wizard_math_and_generators():
    print("--- [1/3] Testing Bell Wizard Calculation & Math ---")

    # 1. Test 1 lesson: 0 breaks
    b1 = _generate_bells_list(count=1, start_str="09:15", lesson_dur=45, breaks=[])
    assert len(b1) == 1
    assert b1[0] == (1, "09:15", "10:00", 0)
    print("  [OK] 1 lesson generation verified (09:15-10:00, break 0).")

    # 2. Test 8 lessons with arbitrary start, arbitrary duration, arbitrary breaks
    breaks_8 = [12, 17, 13, 8, 15, 10, 5]
    b8 = _generate_bells_list(count=8, start_str="08:42", lesson_dur=38, breaks=breaks_8)
    assert len(b8) == 8

    # Lesson 1: 08:42 -> 08:42 + 38 = 09:20, break 12 -> next starts at 09:32
    assert b8[0] == (1, "08:42", "09:20", 12)
    # Lesson 2: 09:32 -> 09:32 + 38 = 10:10, break 17 -> next starts at 10:27
    assert b8[1] == (2, "09:32", "10:10", 17)
    # Lesson 3: 10:27 -> 10:27 + 38 = 11:05, break 13 -> next starts at 11:18
    assert b8[2] == (3, "10:27", "11:05", 13)
    # Lesson 4: 11:18 -> 11:18 + 38 = 11:56, break 8 -> next starts at 12:04
    assert b8[3] == (4, "11:18", "11:56", 8)
    # Lesson 5: 12:04 -> 12:04 + 38 = 12:42, break 15 -> next starts at 12:57
    assert b8[4] == (5, "12:04", "12:42", 15)
    # Lesson 6: 12:57 -> 12:57 + 38 = 13:35, break 10 -> next starts at 13:45
    assert b8[5] == (6, "12:57", "13:35", 10)
    # Lesson 7: 13:45 -> 13:45 + 38 = 14:23, break 5 -> next starts at 14:28
    assert b8[6] == (7, "13:45", "14:23", 5)
    # Lesson 8: 14:28 -> 14:28 + 38 = 15:06, break 0
    assert b8[7] == (8, "14:28", "15:06", 0)
    print("  [OK] 8 lessons arbitrary calculation verified.")

    # 3. Test default breaks helper
    assert _init_default_breaks(1) == []
    assert _init_default_breaks(2) == [10]
    assert _init_default_breaks(3) == [10, 15]
    assert _init_default_breaks(5) == [10, 15, 15, 10]
    assert _init_default_breaks(8) == [10, 15, 15, 10, 10, 10, 5]
    print("  [OK] Default breaks initialization verified.")


async def test_database_permanent_and_cleanup():
    print("--- [2/3] Testing DB Permanent Bell Schedule & Obsolete Lesson Cleanup ---")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Initially seed 8 lessons
        for i in range(1, 9):
            await set_bell_schedule_item(
                session=session,
                lesson_number=i,
                start_time=f"0{8+i//2}:{30 if i%2 else 15}",
                end_time=f"0{8+i//2}:{10 if i%2 else 55}",
                break_duration=10,
                specific_date=None
            )
        bells_initial = await get_bell_schedule(session)
        assert len(bells_initial) == 8, "Expected 8 initial bells"

        # Now simulate saving a 4-lesson schedule via wizard
        b4 = _generate_bells_list(count=4, start_str="08:30", lesson_dur=40, breaks=[10, 15, 15])
        for l_num, s_t, e_t, brk in b4:
            await set_bell_schedule_item(
                session=session,
                lesson_number=l_num,
                start_time=s_t,
                end_time=e_t,
                break_duration=brk,
                specific_date=None
            )

        # Cleanup obsolete records beyond count 4
        await session.execute(
            delete(BellSchedule).where(
                BellSchedule.specific_date.is_(None),
                BellSchedule.lesson_number > 4
            )
        )
        await session.commit()

        bells_after = await get_bell_schedule(session)
        assert len(bells_after) == 4, f"Expected 4 bells after saving 4-lesson schedule, got {len(bells_after)}"
        assert [b.lesson_number for b in bells_after] == [1, 2, 3, 4]
        assert bells_after[0].start_time == "08:30"
        assert bells_after[0].end_time == "09:10"
        assert bells_after[0].break_duration == 10
        print("  [OK] Permanent schedule update & obsolete records cleanup verified.")


async def test_date_specific_bells():
    print("--- [3/3] Testing Date-Specific Bell Schedule Saving ---")

    async with async_session_factory() as session:
        target_d = date(2026, 9, 20)
        from backend.db.crud import save_bulk_date_bells

        custom_bells = _generate_bells_list(count=5, start_str="09:00", lesson_dur=35, breaks=[5, 10, 10, 5])
        await save_bulk_date_bells(session, target_d, custom_bells)

        date_bells = await get_bell_schedule_for_date(session, target_d)
        assert len(date_bells) == 5
        assert date_bells[0].start_time == "09:00"
        assert date_bells[0].end_time == "09:35"
        assert date_bells[0].break_duration == 5
        assert date_bells[-1].lesson_number == 5
        print("  [OK] Date-specific bell schedule saving verified.")


async def main():
    test_wizard_math_and_generators()
    await test_database_permanent_and_cleanup()
    await test_date_specific_bells()
    print("\n=== ALL BELL WIZARD TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(main())
