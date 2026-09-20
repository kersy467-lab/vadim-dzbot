import asyncio
import os
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_daily_facts.db"

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from backend.db.session import async_session_factory, init_db
from backend.db.models import DailyFact
from backend.bot.services.facts import get_or_generate_daily_fact, get_or_generate_hourly_fact, format_fact_telegram_message
from backend.bot.keyboards.main_menu import get_main_keyboard
from backend.main import app

async def run_tests():
    print("--- [1] Initializing DB and checking DailyFact table creation ---")
    await init_db()
    
    test_date = date(2026, 12, 31)
    async with async_session_factory() as session:
        # Clean up any leftover test date
        await session.execute(delete(DailyFact).where(DailyFact.date == test_date))
        await session.commit()

        print("--- [2] Testing get_or_generate_slot_fact (every 30m) ---")
        from backend.bot.services.facts import get_or_generate_slot_fact
        fact_10_00 = await get_or_generate_slot_fact(session, target_date=test_date, target_hour=10, target_minute=0)
        assert fact_10_00 is not None, "Fact should not be None"
        assert fact_10_00.date == test_date, f"Expected {test_date}, got {fact_10_00.date}"
        assert fact_10_00.hour == 10 and fact_10_00.minute == 0, f"Expected 10:00, got {fact_10_00.hour}:{fact_10_00.minute}"
        assert fact_10_00.title, "Title should not be empty"
        id_10_00 = fact_10_00.id
        title_10_00 = fact_10_00.title
        formatted = format_fact_telegram_message(fact_10_00)
        assert "💡" in formatted and title_10_00 in formatted, "Formatter failed"
        assert "Интересный факт" in formatted
        assert "Каждый день — новое открытие!" in formatted
        assert "10:00" not in formatted and "31.12.2026" not in formatted, "Date/time should be removed from header"
        print(f"[OK] Generated fact for {test_date} 10:00: '{title_10_00}' [{fact_10_00.category}]")

        # Call again for same 30m slot - must return exact same DB record
        fact_10_00_repeat = await get_or_generate_slot_fact(session, target_date=test_date, target_hour=10, target_minute=15)
        assert id_10_00 == fact_10_00_repeat.id, f"Expected same fact id, got {id_10_00} vs {fact_10_00_repeat.id}"
        print("[OK] Identical fact strictly returned for the same 30m slot (10:00 - 10:29).")

        # Test 10:30 slot - must generate new record
        fact_10_30 = await get_or_generate_slot_fact(session, target_date=test_date, target_hour=10, target_minute=30)
        assert fact_10_30.id != id_10_00, "Expected different fact id for 10:30 vs 10:00!"
        assert fact_10_30.hour == 10 and fact_10_30.minute == 30
        print(f"[OK] Successfully rotated to new fact for 10:30: '{fact_10_30.title}'")
        print("[OK] Clean Telegram HTML message formatting without date/time verified.")

        # Verify that past fact (10:00) was automatically deleted from storage and ONLY current fact (10:30) remains
        old_fact_res = await session.execute(select(DailyFact).where(DailyFact.id == id_10_00))
        assert old_fact_res.scalars().first() is None, "Past fact was not deleted! Storage must keep only the current fact."
        current_fact_res = await session.execute(select(DailyFact).where(DailyFact.id == fact_10_30.id))
        assert current_fact_res.scalars().first() is not None, "Current fact must be present in storage."
        print("[OK] Verified: past fact (10:00) was automatically deleted and only current fact (10:30) is stored.")

        # Clean up test date
        await session.execute(delete(DailyFact).where(DailyFact.date == test_date))
        await session.commit()

    print("--- [3] Testing Main Keyboard for 💡 Интересный факт button ---")
    kb = get_main_keyboard(is_admin=False)
    all_buttons = [btn.text for row in kb.keyboard for btn in row]
    assert "💡 Интересный факт" in all_buttons, "Button '💡 Интересный факт' missing from main keyboard!"
    print("[OK] '💡 Интересный факт' button present in main keyboard.")

    print("--- [4] Testing GET /api/facts/today FastAPI endpoint ---")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/facts/today")
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}: {res.text}"
        data = res.json()
        assert "date" in data, "Missing date in response"
        assert "hour" in data, "Missing hour in response"
        assert "category" in data, "Missing category in response"
        assert "title" in data, "Missing title in response"
        assert "fact" in data, "Missing fact in response"
        print(f"[OK] /api/facts/today returned 200 OK for hour {data['hour']}: '{data['title']}' ({data['category']})")

    print("\n=== ALL HOURLY FACTS TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
