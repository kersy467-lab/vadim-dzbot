import asyncio
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_suite.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.seed import seed_initial_data
from backend.db.crud import (
    get_all_subjects, create_homework, get_homework_by_id, delete_homework,
    get_homework_for_date, get_homework_by_subject
)
from backend.bot.handlers.admin.homework import (
    escape_md, find_subject_by_text, get_upcoming_or_fallback_dates,
    build_subjects_keyboard_grid, build_date_keyboard, SUBJECT_ALIASES
)

USER_EXACT_TEXT = """Классификация служебных частей речи

Учить все, что написано по 1 заданию

№1 *30"""

OTHER_TRICKY_TEXTS = [
    "Упр. 15, вставить пропущенные буквы: пр_бежать, не_был, _тся_/_ться_",
    "Тест [вариант 1], задания 1-10; *учить правила*",
    "Сочинение `Что такое добро?` на стр. 45-50",
    "Формула: a_1 + a_2 * x_3 <= [10]",
]


async def run_audit():
    print("==================================================")
    print("   TESTING HOMEWORK FIXES FOR ALL 14 SUBJECTS     ")
    print("==================================================")

    # 1. Test Markdown Escaping on User's Exact Problematic Text
    print("\n--- 1. Testing Markdown Escaping on Exact User Input ---")
    escaped = escape_md(USER_EXACT_TEXT)
    print("Original text:\n", repr(USER_EXACT_TEXT))
    print("Escaped text:\n", repr(escaped))
    assert r"\*30" in escaped, "Single asterisk must be escaped as \\*30!"
    print("[OK] User's exact input successfully escaped without Markdown entity errors!")

    for tricky in OTHER_TRICKY_TEXTS:
        esc = escape_md(tricky)
        assert "_" not in esc.replace(r"\_", ""), "All unescaped underscores must be escaped"
        assert "*" not in esc.replace(r"\*", ""), "All unescaped asterisks must be escaped"
        assert "[" not in esc.replace(r"\[", ""), "All unescaped brackets must be escaped"
    print(f"[OK] Verified {len(OTHER_TRICKY_TEXTS)} additional tricky texts with _, *, [, `.")

    # 2. Test DB Seeding and Subjects
    print("\n--- 2. Checking Subjects in Database ---")
    async with async_session_factory() as session:
        await seed_initial_data(session)
        subjects = await get_all_subjects(session)
        print(f"Total subjects loaded: {len(subjects)}")
        assert len(subjects) >= 14, f"Expected at least 14 subjects, got {len(subjects)}"

        subject_names = [s.name for s in subjects]
        print("Subjects in database:")
        for i, s in enumerate(subjects, 1):
            print(f"  {i:2d}. id={s.id:2d} -> {s.name}")

        assert "Русский язык" in subject_names, "'Русский язык' must be in subjects"
        assert "Литература" in subject_names, "'Литература' must be in subjects"

        # 3. Test Text Aliases & Fuzzy Finding for ALL 14 Subjects
        print("\n--- 3. Testing Subject Text Input & Aliases ---")
        test_queries = [
            ("русский", "Русский язык"),
            ("рус", "Русский язык"),
            ("рус яз", "Русский язык"),
            ("Русский язык", "Русский язык"),
            ("литра", "Литература"),
            ("лит-ра", "Литература"),
            ("литература", "Литература"),
            ("алг", "Алгебра"),
            ("алгебра", "Алгебра"),
            ("матеша", "Алгебра"),
            ("геома", "Геометрия"),
            ("геометрия", "Геометрия"),
            ("физ", "Физика"),
            ("физика", "Физика"),
            ("хим", "Химия"),
            ("химия", "Химия"),
            ("био", "Биология"),
            ("биология", "Биология"),
            ("ист", "История"),
            ("история", "История"),
            ("общество", "Обществознание"),
            ("общага", "Обществознание"),
            ("обществознание", "Обществознание"),
            ("гео", "География"),
            ("география", "География"),
            ("англ", "Английский язык"),
            ("английский", "Английский язык"),
            ("инфа", "Информатика"),
            ("информатика", "Информатика"),
            ("физра", "Физкультура"),
            ("физкультура", "Физкультура"),
            ("обж", "ОБЖ"),
        ]

        for query, expected in test_queries:
            matched = find_subject_by_text(query, subjects)
            assert matched is not None, f"Query '{query}' should match subject '{expected}'"
            assert matched.name == expected, f"Query '{query}' matched '{matched.name}', expected '{expected}'"
        print(f"[OK] All {len(test_queries)} text queries and aliases correctly matched!")

        # 4. Test 2-column Subject Grid
        print("\n--- 4. Testing Subject Selection Grid Keyboard ---")
        kb_grid = build_subjects_keyboard_grid(subjects)
        # Should have rows of 2 buttons + 1 cancel button
        assert len(kb_grid.inline_keyboard) >= 8, "Expected at least 8 rows in 2-column layout"
        assert len(kb_grid.inline_keyboard[0]) == 2, "Row 0 must contain 2 subject buttons"
        assert kb_grid.inline_keyboard[-1][0].text == "❌ Отмена"
        print(f"[OK] 2-column grid verified: {len(kb_grid.inline_keyboard)} rows (compact for mobile).")

        # 5. Test Date Generation & Fallback for ALL Subjects
        print("\n--- 5. Testing Upcoming & Fallback Dates for Every Subject ---")
        today = date(2026, 9, 4)  # Friday
        for s in subjects:
            dates, is_sched = await get_upcoming_or_fallback_dates(session, s.id, from_date=today + timedelta(days=1), limit=4)
            assert len(dates) == 4, f"Subject {s.name} must have 4 upcoming date options"
            # Ensure Sunday (isoweekday 7) is never offered
            for d in dates:
                assert d.isoweekday() != 7, f"Sunday {d} should not be offered in dates for {s.name}"
            # Test keyboard building
            kb = build_date_keyboard(dates, selected_date=dates[0], is_scheduled=is_sched)
            assert len(kb.inline_keyboard) == 6  # 4 dates + calendar + cancel
            assert "✅" in kb.inline_keyboard[0][0].text
        print("[OK] Fallback date generation and interactive keyboard verified for all subjects.")

        # 6. Test Creating, Reading, and Deleting Homework for ALL 14 Subjects
        print("\n--- 6. Creating & Verifying Homework in DB for ALL 14 Subjects ---")
        created_hw_ids = []
        for s in subjects:
            # We use the exact problematic text for Russian, and other tricky texts for other subjects
            hw_desc = USER_EXACT_TEXT if s.name == "Русский язык" else f"Задание по предмету {s.name}: {OTHER_TRICKY_TEXTS[s.id % len(OTHER_TRICKY_TEXTS)]}"
            hw = await create_homework(
                session=session,
                subject_id=s.id,
                due_date=today + timedelta(days=3),
                assigned_date=today,
                description=hw_desc,
                attachments=[],
                created_by=12345
            )
            assert hw.id is not None
            created_hw_ids.append(hw.id)

            # Retrieve from DB and verify
            fetched = await get_homework_by_id(session, hw.id)
            assert fetched is not None
            assert fetched.subject_id == s.id
            assert fetched.description == hw_desc

        print(f"[OK] Successfully created and verified HW in database for all {len(created_hw_ids)} subjects!")

        # Clean up created test homework
        for hid in created_hw_ids:
            await delete_homework(session, hid)
        print("[OK] Cleaned up test homework records.")

    print("\n==================================================")
    print("   ALL AUDIT CHECKS PASSED WITH ZERO ERRORS!      ")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_audit())
