import asyncio
import os
import sys
from datetime import date, timedelta
from fastapi.testclient import TestClient

# Ensure backend can be imported and uses isolated SQLite for local tests
sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_suite.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"
os.environ.setdefault("ADMIN_ID", "999999999")

from backend.config import settings, get_today
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_suite.db"
from backend.db.session import init_db, async_session_factory, engine

from backend.db.seed import seed_initial_data
from backend.db.crud import (
    create_user, get_user_by_tg_id, update_user_role, toggle_user_notifications,
    get_notifiable_users, get_active_users, get_pending_users,
    create_or_update_group_chat, get_group_chat_by_id, update_group_chat_role,
    get_approved_group_chats, get_all_subjects, get_bell_schedule,
    set_schedule_item, get_schedule_for_day, get_schedule_for_date,
    set_permanent_schedule_item, set_date_schedule_item, get_full_week_schedule,
    create_substitution, get_substitutions_for_date,
    create_homework, get_homework_for_date, get_homework_by_subject,
    toggle_homework_completion, get_user_homework_status,
    create_subject, delete_subject, set_bell_break_duration,
    get_all_duty_groups, get_current_duty_info, set_class_setting, create_or_update_duty_group,
    save_bulk_date_schedule, save_bulk_permanent_schedule, clear_date_schedule,
    get_bell_schedule_for_date, clear_date_bells, save_bulk_date_bells, clear_all_duty_members,
    find_upcoming_dates_for_subject, auto_shift_active_homeworks,
    delete_homework, get_homework_by_id, get_recent_active_homeworks,
    delete_user, get_all_users, update_user_tester_status
)



from backend.bot.handlers.schedule import format_day_schedule
from backend.bot.handlers.admin import parse_schedule_text, parse_bells_text
from backend.bot.keyboards.main_menu import get_main_keyboard


from backend.bot.keyboards.inline import (
    get_schedule_keyboard, get_day_picker_keyboard, get_homework_keyboard,
    get_homework_item_keyboard, get_admin_approval_keyboard
)
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_notify_confirm_keyboard,
    get_hw_notify_keyboard
)

from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.handlers.group import get_admin_chat_approval_keyboard
from backend.main import app, bot, dp

async def test_database_and_crud():
    print("--- [1/4] Testing DB initialization, Seeding & Duty Groups ---")
    async with engine.begin() as conn:
        from backend.db.models import Base
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await seed_initial_data(session)
        subjects = await get_all_subjects(session)
        bells = await get_bell_schedule(session)
        duty_groups = await get_all_duty_groups(session)

        assert len(subjects) > 0, "Subjects should be seeded"
        assert len(bells) == 8, "8 Bell items should be seeded"
        assert len(duty_groups) == 6, "6 Duty groups (0 to 5) should be seeded in September"
        print(f"[OK] Seeded {len(subjects)} subjects, {len(bells)} bells, {len(duty_groups)} duty groups.")

        # Test duty roster retrieval in September (Group 0 active)
        active_g, all_g = await get_current_duty_info(session)
        assert active_g is not None
        assert active_g.group_number == 0, "Group 0 must be active in September!"
        assert len(all_g) == 6

        # Test notification on duty change
        from backend.bot.services.notifier import notify_duty_change_if_needed
        class MockBotDuty:
            def __init__(self):
                self.sent_messages = []
            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent_messages.append((chat_id, text))
        mb_duty = MockBotDuty()
        notified = await notify_duty_change_if_needed(mb_duty, session, force=True)
        assert notified is True
        print("[OK] Duty change notification sending verified.")

        # Test manual duty setting override
        await set_class_setting(session, "current_duty_group", "4")
        active_g4, _ = await get_current_duty_info(session)
        assert active_g4.group_number == 4
        # Reset manual override
        await set_class_setting(session, "current_duty_group", "")
        print("[OK] Duty roster and manual override verified.")

        # Test October rotation and Group 0 deletion
        import backend.config as cfg_module
        orig_get_today = cfg_module.get_today
        try:
            # Simulate October 1st, 2026
            cfg_module.get_today = lambda: date(2026, 10, 1)
            oct_active_g, oct_all_g = await get_current_duty_info(session)
            assert len(oct_all_g) == 5, "Group 0 must be deleted after September!"
            assert all(g.group_number != 0 for g in oct_all_g), "Group 0 must not be in duty groups in October!"
            assert oct_active_g.group_number == 1, "Week 1 in October must rotate to Group 1!"

            # Simulate October 5th, 2026 (Monday of week 2)
            cfg_module.get_today = lambda: date(2026, 10, 5)
            oct_active_g2, _ = await get_current_duty_info(session)
            assert oct_active_g2.group_number == 2, "Week 2 in October must rotate to Group 2!"
            print("[OK] Group 0 deletion after September and October 1-5 rotation verified.")
        finally:
            cfg_module.get_today = orig_get_today
            await set_class_setting(session, "current_duty_group", "")
            await get_all_duty_groups(session)



        # Test subject add/delete
        new_s = await create_subject(session, "Астрономия")
        assert new_s.name == "Астрономия"
        del_ok = await delete_subject(session, new_s.id)
        assert del_ok is True
        print("[OK] Subject creation and deletion verified.")

        # Test break duration and automatic recalculation
        updated_bell = await set_bell_break_duration(session, lesson_number=1, break_duration=20)
        assert updated_bell.break_duration == 20
        bells_check = await get_bell_schedule(session)
        bell_2 = next(b for b in bells_check if b.lesson_number == 2)
        assert bell_2.start_time == "09:30", f"Lesson 2 start time should recalculate to 09:30, got {bell_2.start_time}"
        print("[OK] Bell break duration edit & automatic schedule recalculation verified.")


    print("--- [2/4] Testing User & Group CRUD ---")
    async with async_session_factory() as session:
        student = await create_user(session, tg_id=111222, full_name="Тестовый Ученик", username="test_student", role="pending")
        assert student.role == "pending"

        student = await update_user_role(session, 111222, "student")
        assert student.role == "student"
        assert student.is_tester is False

        student = await update_user_tester_status(session, 111222, True)
        assert student.is_tester is True

        student = await update_user_tester_status(session, 111222, False)
        assert student.is_tester is False

        group = await create_or_update_group_chat(session, chat_id=-100999, title="11-Б Класс", added_by=111222, role="pending")
        assert group.role == "pending"
        group = await update_group_chat_role(session, -100999, "approved")
        assert group.role == "approved"

        print("[OK] User and Group CRUD verified.")

    print("--- [3/4] Testing Permanent vs Date Schedule & HW Media ---")
    async with async_session_factory() as session:
        subj1 = subjects[0]
        subj2 = subjects[1]
        today = get_today()
        day_of_week = today.isoweekday()

        # 1. Permanent Schedule
        await set_permanent_schedule_item(session, day_of_week=day_of_week, lesson_number=1, subject_id=subj1.id)
        perm_sched = await get_schedule_for_date(session, today)
        assert len(perm_sched) == 1
        assert perm_sched[0].subject_id == subj1.id
        print("[OK] Permanent schedule fallback verified.")

        # 2. Date-specific Schedule Override
        await set_date_schedule_item(session, target_date=today, lesson_number=1, subject_id=subj2.id)
        date_sched = await get_schedule_for_date(session, today)
        assert len(date_sched) == 1
        assert date_sched[0].subject_id == subj2.id
        print("[OK] Date-specific schedule override verified.")

        # 3. Homework with multiple media attachments
        attachments = [
            {"type": "photo", "file_id": "test_photo_id_1"},
            {"type": "document", "file_id": "test_doc_id_1", "file_name": "task.pdf"}
        ]
        hw = await create_homework(
            session=session,
            subject_id=subj1.id,
            due_date=today,
            description="Упр. 15, стр. 42",
            attachments=attachments
        )
        hw_list = await get_homework_for_date(session, today)
        assert len(hw_list) == 1
        assert len(hw_list[0].attachments) == 2
        assert hw_list[0].attachments[0]["type"] == "photo"
        assert hw_list[0].attachments[1]["type"] == "document"
        print("[OK] Homework media support (photo + document) verified.")

        is_done = await toggle_homework_completion(session, user_id=student.id, hw_id=hw.id)
        assert is_done is True
        st = await get_user_homework_status(session, user_id=student.id, hw_id=hw.id)
        assert st.is_completed is True

        cal_kb = get_inline_calendar("sched", today.year, today.month)
        assert len(cal_kb.inline_keyboard) >= 4
        print("[OK] Calendar verified.")

        # 4. Test Text Schedule Parser and Bulk Saving
        raw_text = """
        1. Геометрия
        2. Физика
        3. Русский язык
        4. Литература
        5. История
        6. Информатика
        """
        parsed = parse_schedule_text(raw_text)
        assert len(parsed) == 6
        assert parsed[0] == (1, "Геометрия")
        assert parsed[5] == (6, "Информатика")

        bulk_items = await save_bulk_date_schedule(session, today, parsed)
        assert len(bulk_items) == 6
        loaded = await get_schedule_for_date(session, today)
        assert len(loaded) == 6
        assert loaded[0].subject.name == "Геометрия"
        print("[OK] Bulk schedule parser and bulk date schedule saving verified.")

        # 5. Test Resetting date schedule
        await clear_date_schedule(session, today)
        fallback = await get_schedule_for_date(session, today)
        assert len(fallback) == 1
        assert fallback[0].subject_id == subj1.id
        print("[OK] Resetting date schedule to permanent fallback verified.")

        # 6. Test Ultra-Flexible Schedule Parser (no formatting requirements)
        # Comma-separated:
        p_comma = parse_schedule_text("Алгебра, Физика, Литература, Химия")
        assert len(p_comma) == 4
        assert p_comma[0] == (1, "Алгебра")
        assert p_comma[3] == (4, "Химия")

        # Bulleted, lowercase:
        p_bullet = parse_schedule_text("- геометрия\n* биология\n• история")
        assert len(p_bullet) == 3
        assert p_bullet[0] == (1, "Геометрия") # auto-capitalized
        assert p_bullet[1] == (2, "Биология")
        assert p_bullet[2] == (3, "История")

        # Single line inline numbered:
        p_inline = parse_schedule_text("1. Информатика 2. ОБЖ 3. Астрономия")
        assert len(p_inline) == 3
        assert p_inline[0] == (1, "Информатика")
        assert p_inline[2] == (3, "Астрономия")
        print("[OK] Ultra-flexible schedule parser (comma, bulleted, lowercase, inline) verified.")

        # 7. Test Bell Schedule Parser & Date-Specific Bells
        b_parsed = parse_bells_text("1. 08:30 - 09:05\n2. 09:15 - 09:50")
        assert len(b_parsed) == 2
        assert b_parsed[0][1] == "08:30"
        assert b_parsed[0][2] == "09:05"
        assert b_parsed[1][3] == 10  # 10 min break

        # Date-specific bell schedule saving
        await save_bulk_date_bells(session, today, [(1, "08:30", "09:05", 10), (2, "09:15", "09:50", 10)])
        loaded_bells = await get_bell_schedule_for_date(session, today)
        assert len(loaded_bells) == 2
        assert loaded_bells[0].end_time == "09:05"

        # Clear date bells fallback to permanent standard bells
        await clear_date_bells(session, today)
        perm_bells = await get_bell_schedule_for_date(session, today)
        assert len(perm_bells) == 8
        assert perm_bells[0].end_time == "09:10"
        print("[OK] Date-specific bells and fallback to standard bells verified.")

        # 8. Test Clearing Duty Roster
        await clear_all_duty_members(session)
        cleared_groups = await get_all_duty_groups(session)
        for cg in cleared_groups:
            assert cg.members == "Состав не назначен"
        print("[OK] Duty roster clearing verified.")

        # 9. Test Permanent Schedule Update Freezing Past Dates
        from sqlalchemy import delete, select
        from backend.db.models import Schedule
        past_monday = date(2026, 9, 7)
        future_monday = date(2026, 9, 21)
        await session.execute(delete(Schedule).where(Schedule.specific_date == past_monday))
        await session.commit()
        await save_bulk_permanent_schedule(session, 1, [(1, "Алгебра"), (2, "Физика")])

        await session.execute(delete(Schedule).where(Schedule.specific_date == past_monday))
        await session.commit()
        from backend.db.crud import freeze_past_schedules_for_weekday
        await freeze_past_schedules_for_weekday(session, 1, up_to_date=date(2026, 9, 14))
        await save_bulk_permanent_schedule(session, 1, [(1, "Химия"), (2, "Биология")])

        # Verify past Monday kept the old schedule!
        past_sched = await get_schedule_for_date(session, past_monday)
        assert len(past_sched) == 2
        assert past_sched[0].subject.name == "Алгебра"
        assert past_sched[1].subject.name == "Физика"

        # Verify future Monday got the new schedule!
        future_sched = await get_schedule_for_date(session, future_monday)
        assert len(future_sched) == 2
        assert future_sched[0].subject.name == "Химия"
        assert future_sched[1].subject.name == "Биология"
        print("[OK] Permanent schedule updates affect only future dates (past dates frozen) verified.")

        # 9b. Test 1 September and Earlier Dates Exclusion (No Lessons)
        sept8_test = date(2026, 9, 8)
        await save_bulk_permanent_schedule(session, 2, [(1, "Геометрия"), (2, "Информатика")])
        await session.execute(delete(Schedule).where(Schedule.specific_date == sept8_test))
        await session.commit()
        await freeze_past_schedules_for_weekday(session, 2, up_to_date=date(2026, 9, 15))

        # Verify September 1st and August return NO schedule (empty list)
        sched_sept1 = await get_schedule_for_date(session, date(2026, 9, 1))
        assert sched_sept1 == [], "1 September must have NO lessons scheduled!"
        sched_august = await get_schedule_for_date(session, date(2026, 8, 25))
        assert sched_august == [], "August dates must have NO lessons scheduled!"

        # Verify September 8th (next Tuesday) DOES have lessons
        sched_sept8 = await get_schedule_for_date(session, date(2026, 9, 8))
        assert len(sched_sept8) == 2
        assert sched_sept8[0].subject.name == "Геометрия"

        # Verify homework scheduling returns False on or before September 1st
        from backend.db.crud.homework import is_subject_scheduled_on_date
        all_subs_temp = await get_all_subjects(session)
        temp_map = {s.name: s.id for s in all_subs_temp}
        geom_id = temp_map["Геометрия"]
        assert await is_subject_scheduled_on_date(session, geom_id, date(2026, 9, 1)) is False
        assert await is_subject_scheduled_on_date(session, geom_id, date(2026, 8, 25)) is False
        assert await is_subject_scheduled_on_date(session, geom_id, date(2026, 9, 8)) is True

        # Verify academic calendar statuses and badges
        from backend.bot.services.academic_calendar import get_day_special_status, format_day_badge
        st_sept1, txt_sept1 = get_day_special_status(date(2026, 9, 1))
        assert st_sept1 == "vacation" and "1 Сентября" in txt_sept1
        st_aug, txt_aug = get_day_special_status(date(2026, 8, 25))
        assert st_aug == "vacation" and "Летние каникулы" in txt_aug
        assert format_day_badge(date(2026, 9, 1), 1, False) == "🔔1"

        # Verify message text for 1 September and August
        from backend.bot.handlers.schedule import format_day_schedule
        msg_sept1 = await format_day_schedule(session, date(2026, 9, 1))
        assert "1 Сентября" in msg_sept1 and "уроков не было" in msg_sept1
        msg_aug = await format_day_schedule(session, date(2026, 8, 25))
        assert "Летние каникулы" in msg_aug
        print("[OK] September 1st and earlier dates schedule exclusion strictly verified.")

        # --- Test Smart Homework & Auto-Shift ---
        all_subs = await get_all_subjects(session)
        subj_map = {s.name: s.id for s in all_subs}
        chem_id = subj_map["Химия"]

        # 1. Upcoming dates for Chemistry (Monday)
        chem_dates = await find_upcoming_dates_for_subject(session, chem_id, from_date=date(2026, 9, 15), limit=2)
        assert len(chem_dates) >= 1
        assert chem_dates[0] == date(2026, 9, 21), f"Expected next Monday 21.09, got {chem_dates[0]}"

        # 2. Create homework for Chemistry due 2026-09-21, assigned on 2026-09-14
        hw_active = await create_homework(
            session=session,
            subject_id=chem_id,
            due_date=date(2026, 9, 21),
            assigned_date=date(2026, 9, 14),
            description="Параграф 5, упр. 1-4"
        )
        assert hw_active.assigned_date == date(2026, 9, 14)

        # 3. Create a past homework (due in the past)
        today = get_today()
        hw_past = await create_homework(
            session=session,
            subject_id=chem_id,
            due_date=today - timedelta(days=2),
            assigned_date=today - timedelta(days=7),
            description="Старое сданное задание"
        )
        past_orig_due = hw_past.due_date

        # 4. Schedule change occurs: Chemistry added earlier on a specific date (earlier than hw_active due_date)
        shift_target_date = today
        await set_date_schedule_item(session, shift_target_date, 1, chem_id)

        # 5. Run auto-shift
        shifted = await auto_shift_active_homeworks(session, affected_subject_id=chem_id)
        assert len(shifted) >= 1

        # Check that active homework shifted to the earlier date!
        await session.refresh(hw_active)
        assert hw_active.due_date == shift_target_date, f"Expected shifted to {shift_target_date}, got {hw_active.due_date}"

        # Check that past homework was NOT touched (remained closed/frozen)
        await session.refresh(hw_past)
        assert hw_past.due_date == past_orig_due, "Past homework should not be shifted!"
        print("[OK] Smart homework upcoming dates and schedule auto-shift verified.")

        # --- Test Multi-Attachment Homework ---
        multi_att = [
            {"type": "photo", "file_id": "photo_file_id_1"},
            {"type": "photo", "file_id": "photo_file_id_2"},
            {"type": "document", "file_id": "doc_file_id_1", "file_name": "uchebnik.pdf"}
        ]
        hw_multi = await create_homework(
            session=session,
            subject_id=chem_id,
            due_date=date(2026, 9, 21),
            assigned_date=date(2026, 9, 14),
            description="Прочитать параграф и выполнить упражнения из PDF",
            attachments=multi_att
        )
        assert len(hw_multi.attachments) == 3
        assert hw_multi.attachments[0]["file_id"] == "photo_file_id_1"
        assert hw_multi.attachments[1]["file_id"] == "photo_file_id_2"
        assert hw_multi.attachments[2]["file_name"] == "uchebnik.pdf"
        print("[OK] Multi-attachment homework (multiple photos and files) verified.")

        # Test homework deletion
        del_res = await delete_homework(session, hw_multi.id)
        assert del_res is True
        del_check = await get_homework_by_id(session, hw_multi.id)
        assert del_check is None
        print("[OK] Homework deletion verified.")

        # --- Test Per-User Checklist Isolation ---
        user_a = await create_user(session, tg_id=888001, full_name="User Alice", role="student")
        user_b = await create_user(session, tg_id=888002, full_name="User Bob", role="student")

        hw_test = await create_homework(
            session=session,
            subject_id=chem_id,
            due_date=date(2026, 9, 25),
            assigned_date=date(2026, 9, 18),
            description="Проверить изоляцию чеклиста"
        )

        # Initially both uncompleted
        st_a = await get_user_homework_status(session, user_a.id, hw_test.id)
        st_b = await get_user_homework_status(session, user_b.id, hw_test.id)
        assert (st_a is None or not st_a.is_completed)
        assert (st_b is None or not st_b.is_completed)

        # Alice toggles to completed
        new_st_a = await toggle_homework_completion(session, user_a.id, hw_test.id)
        assert new_st_a is True

        # Check: Alice is completed, Bob is still NOT completed
        chk_a = await get_user_homework_status(session, user_a.id, hw_test.id)
        chk_b = await get_user_homework_status(session, user_b.id, hw_test.id)
        assert chk_a.is_completed is True
        assert (chk_b is None or not chk_b.is_completed)

        # Bob toggles to completed
        new_st_b = await toggle_homework_completion(session, user_b.id, hw_test.id)
        assert new_st_b is True

        # Alice un-completes
        new_st_a2 = await toggle_homework_completion(session, user_a.id, hw_test.id)
        assert new_st_a2 is False

        # Verify Bob remains completed while Alice is now uncompleted (and row deleted to keep DB clean)
        chk_a2 = await get_user_homework_status(session, user_a.id, hw_test.id)
        chk_b2 = await get_user_homework_status(session, user_b.id, hw_test.id)
        assert (chk_a2 is None or not chk_a2.is_completed)
        assert chk_b2.is_completed is True
        print("[OK] User checklist isolation strictly verified (Alice vs Bob completely independent).")

        # --- Test Past Homework Filter (Yesterday & Earlier Not Shown) ---
        today_ref = get_today()
        yesterday = today_ref - timedelta(days=1)
        hw_yesterday = await create_homework(
            session=session,
            subject_id=chem_id,
            due_date=yesterday,
            assigned_date=yesterday - timedelta(days=2),
            description="Старое вчерашнее ДЗ"
        )

        active_subj_hw = await get_homework_by_subject(session, chem_id, from_date=today_ref)
        yesterday_ids = [h.id for h in active_subj_hw]
        assert hw_yesterday.id not in yesterday_ids, "Yesterday homework must NOT be returned by get_homework_by_subject!"

        recent_active = await get_recent_active_homeworks(session)
        recent_ids = [h.id for h in recent_active]
        assert hw_yesterday.id not in recent_ids, "Yesterday homework must NOT be in recent_active_homeworks!"
        print("[OK] Past homework (yesterday and earlier) exclusion verified.")

        # --- Test Automatic Past Checklist Cleanup ---
        from backend.db.crud.homework import cleanup_past_homework_statuses
        await toggle_homework_completion(session, user_b.id, hw_yesterday.id)
        assert (await get_user_homework_status(session, user_b.id, hw_yesterday.id)) is not None

        cleaned_count = await cleanup_past_homework_statuses(session, before_date=today_ref)
        assert cleaned_count >= 1

        past_st = await get_user_homework_status(session, user_b.id, hw_yesterday.id)
        assert past_st is None, "Past homework checklist status must be deleted by cleanup!"

        active_st = await get_user_homework_status(session, user_b.id, hw_test.id)
        assert active_st is not None and active_st.is_completed is True
        print("[OK] Automatic checklist cleanup of past homework strictly verified.")

        # --- Test User Deletion ---
        user_c = await create_user(session, tg_id=888003, full_name="User Charlie", role="student")
        await toggle_homework_completion(session, user_c.id, hw_test.id)
        st_c = await get_user_homework_status(session, user_c.id, hw_test.id)
        assert st_c is not None and st_c.is_completed is True

        del_user_res = await delete_user(session, user_c.tg_id)
        assert del_user_res is True

        check_deleted_user = await get_user_by_tg_id(session, user_c.tg_id)
        assert check_deleted_user is None, "Deleted user must not be found in DB!"

        check_deleted_st = await get_user_homework_status(session, user_c.id, hw_test.id)
        assert check_deleted_st is None, "Deleted user's homework status must be wiped!"
        print("[OK] User deletion and related data cleanup verified.")

        # Test rejected user re-applying without DB clearing
        user_rej = await create_user(session, tg_id=888777, full_name="Rejected Student", role="rejected")
        assert user_rej.role == "rejected"
        
        class MockBot:
            def __init__(self):
                self.sent_messages = []
            async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
                self.sent_messages.append((chat_id, text, reply_markup))

        mock_bot = MockBot()
        from backend.bot.handlers.start import register_pending_user_and_notify_admin
        reapplied_user = await register_pending_user_and_notify_admin(
            bot=mock_bot,
            session=session,
            user_id=888777,
            full_name="Reapplied Student",
            username="reapplied"
        )
        assert reapplied_user.role == "pending", "Rejected user re-applying must become pending!"
        assert len(mock_bot.sent_messages) == 1, "Admin must receive approval notification for re-applying user!"
        print("[OK] Rejected user re-applying without DB clearing verified.")

        # Test schedule formatting with substitution
        from backend.bot.handlers.schedule import format_day_schedule
        from backend.db.crud import create_substitution, get_subject_by_name
        sub_subj = await get_subject_by_name(session, "Химия")

        await create_substitution(session, target_date=today, lesson_number=1, old_subject_id=None, new_subject_id=sub_subj.id, is_cancelled=False)

        sched_sub_text = await format_day_schedule(session, today)
        assert "(ЗАМЕНА)" not in sched_sub_text, "Schedule must not write (ЗАМЕНА) in text!"
        assert "Химия" in sched_sub_text, "Substituted subject name must be in schedule text!"
        print("[OK] Schedule clean formatting without (ЗАМЕНА) label verified.")

        # Test schedule cancellation (completely omitted from schedule)
        await create_substitution(session, target_date=today, lesson_number=2, old_subject_id=None, new_subject_id=None, is_cancelled=True)
        sched_cancel_text = await format_day_schedule(session, today)
        assert "**2.**" not in sched_cancel_text, "Cancelled lesson must be completely omitted from schedule!"
        print("[OK] Cancelled lesson completely omitted from schedule verified.")

        # Test admin self-demote and self-delete prevention
        from backend.bot.handlers.admin import cb_toggle_user_role, cb_admin_delete_user_ask
        from backend.db.models import User
        class MockCallback:
            def __init__(self, data, from_user_id):
                self.data = data
                self.from_user = type("Obj", (), {"id": from_user_id, "full_name": "Admin"})()
                self.answered_alerts = []
            async def answer(self, text="", show_alert=False):
                self.answered_alerts.append((text, show_alert))

        admin_self = User(id=99, tg_id=55555, full_name="Secondary Admin", role="admin")
        cb_demote_self = MockCallback("adm_toggle_role_55555", from_user_id=55555)
        await cb_toggle_user_role(cb_demote_self, session, current_user=admin_self)
        assert len(cb_demote_self.answered_alerts) == 1
        assert "Вы не можете снять права администратора с самого себя" in cb_demote_self.answered_alerts[0][0]

        cb_del_self = MockCallback("adm_del_user_ask_55555", from_user_id=55555)
        await cb_admin_delete_user_ask(cb_del_self, session, current_user=admin_self)
        assert len(cb_del_self.answered_alerts) == 1
        assert "Вы не можете удалить самого себя" in cb_del_self.answered_alerts[0][0]
        print("[OK] Admin self-demotion and self-deletion prevention strictly verified.")

        # Test personalized evening digest in PM with individual checklist
        from backend.bot.services.notifier import send_evening_digest
        from backend.db.crud import get_approved_group_chats, get_or_create_subject
        tom = today + timedelta(days=1)
        while tom.isoweekday() in (6, 7):
            tom = tom + timedelta(days=1)
        subj_bio = await get_or_create_subject(session, "Биология")
        subj_geo = await get_or_create_subject(session, "География")
        hw_bio = await create_homework(session, subject_id=subj_bio.id, due_date=tom, description="Параграф 10")
        hw_geo = await create_homework(session, subject_id=subj_geo.id, due_date=tom, description="Карта мира")

        user_alice = await create_user(session, tg_id=111001, full_name="Алиса", role="student")
        user_bob = await create_user(session, tg_id=111002, full_name="Боб", role="student")

        # Alice completes Biology in checklist
        await toggle_homework_completion(session, user_alice.id, hw_bio.id)

        class MockDigestBot:
            def __init__(self):
                self.messages = {}
            async def send_message(self, chat_id, text, parse_mode=None, message_thread_id=None):
                self.messages.setdefault(chat_id, []).append(text)

        digest_bot = MockDigestBot()
        await send_evening_digest(digest_bot, target_date=tom)

        # 1. Verify sent in PM to users, AND to approved group chats
        groups = await get_approved_group_chats(session)
        for g in groups:
            assert g.chat_id in digest_bot.messages, "Evening digest must be sent to approved groups!"

        assert 111001 in digest_bot.messages, "Alice must receive evening digest in PM!"
        assert 111002 in digest_bot.messages, "Bob must receive evening digest in PM!"

        alice_text = digest_bot.messages[111001][0]
        bob_text = digest_bot.messages[111002][0]

        # 2. Verify schedule is present
        assert "Расписание уроков:" in alice_text
        assert "Расписание уроков:" in bob_text

        # 3. Alice: Biology is completed, Geography is uncompleted
        assert "География" in alice_text
        assert "Невыполненные задания" in alice_text
        assert "Уже выполнено по чек-листу: 1" in alice_text

        # 4. Bob: Neither completed -> both uncompleted
        assert "Невыполненные задания" in bob_text
        assert "Биология" in bob_text
        assert "География" in bob_text

        # 5. Alice completes Geography as well -> all done
        for h_item in await get_homework_for_date(session, tom):
            status = await get_user_homework_status(session, user_alice.id, h_item.id)
            if not status or not status.is_completed:
                await toggle_homework_completion(session, user_alice.id, h_item.id)
        digest_bot_2 = MockDigestBot()
        await send_evening_digest(digest_bot_2, target_date=tom)
        alice_text_2 = digest_bot_2.messages[111001][0]
        assert "Все задания на завтра" in alice_text_2
        assert "выполнены!" in alice_text_2
        print("[OK] Personalized evening digest in PM with individual uncompleted homework checklist strictly verified.")






def test_keyboards_and_fastapi():
    print("--- [4/4] Testing Keyboards & FastAPI Endpoints ---")
    main_kb = get_main_keyboard(is_admin=True)
    btn_texts = [b.text for row in main_kb.keyboard for b in row]
    
    assert "🧹 График дежурств" in btn_texts
    assert "☀️ До лета осталось" in btn_texts
    assert "💡 Интересный факт" in btn_texts
    assert "⚙️ Настройки" in btn_texts, "Settings button should be present"
    print("[OK] Main keyboard buttons verified (Duty, Summer, Interesting Fact, and Settings present).")

    adm_kb = get_admin_panel_keyboard()
    adm_cb = [b.callback_data for row in adm_kb.inline_keyboard for b in row]
    assert "admin_delete_hw" in adm_cb, "admin_delete_hw must be present in admin panel"
    assert "admin_delete_user" not in adm_cb, "admin_delete_user removed from main admin panel"
    assert "admin_manage_subjects" not in adm_cb, "admin_manage_subjects removed from main admin panel"
    assert "admin_broadcast_custom" in adm_cb, "admin_broadcast_custom must be present in admin panel"
    assert "admin_edit_date_schedule" in adm_cb
    assert "admin_edit_schedule" in adm_cb
    assert "admin_manage_duty" in adm_cb
    assert "admin_broadcast_schedule" in adm_cb, "admin_broadcast_schedule must be present in admin panel"
    assert "admin_give_coins" in adm_cb, "admin_give_coins must be present in admin panel"
    print("[OK] Admin panel verified: HW delete, urgent broadcast, schedule broadcast, duty announcement, date schedule, permanent schedule, duty roster & give coins verified; redundant buttons removed.")

    # Test Schedule Broadcast Keyboards
    from backend.bot.keyboards.admin_kb import get_schedule_broadcast_day_keyboard, get_schedule_broadcast_destination_keyboard
    day_kb = get_schedule_broadcast_day_keyboard()
    day_cbs = [b.callback_data for row in day_kb.inline_keyboard for b in row]
    assert "bcast_sched_day_today" in day_cbs
    assert "bcast_sched_day_tomorrow" in day_cbs
    assert "bcast_sched_day_cal" in day_cbs

    sched_dest_kb = get_schedule_broadcast_destination_keyboard()
    sched_dest_cbs = [b.callback_data for row in sched_dest_kb.inline_keyboard for b in row]
    assert "bcast_sched_dest_groups" in sched_dest_cbs
    assert "bcast_sched_dest_pm" in sched_dest_cbs
    assert "bcast_sched_dest_all" in sched_dest_cbs

    from backend.bot.keyboards.inline import get_schedule_keyboard
    admin_sched_kb = get_schedule_keyboard(is_admin=True)
    admin_sched_cbs = [b.callback_data for row in admin_sched_kb.inline_keyboard for b in row]
    assert "admin_broadcast_schedule" in admin_sched_cbs
    print("[OK] On-demand schedule broadcast keyboards (day picker, destinations, admin schedule kb) verified.")

    # Test Broadcast destination keyboard
    from backend.bot.keyboards.admin_kb import get_broadcast_destination_keyboard, get_duty_broadcast_destination_keyboard
    bcast_kb = get_broadcast_destination_keyboard()
    bcast_cbs = [b.callback_data for row in bcast_kb.inline_keyboard for b in row]
    assert "bcast_dest_users" in bcast_cbs
    assert "bcast_dest_groups" in bcast_cbs
    assert "bcast_dest_all" in bcast_cbs
    print("[OK] General broadcast destination keyboard (users, groups, all) verified.")

    # Test Duty Broadcast destination keyboard
    duty_bcast_kb = get_duty_broadcast_destination_keyboard()
    duty_bcast_cbs = [b.callback_data for row in duty_bcast_kb.inline_keyboard for b in row]
    assert "duty_bcast_dest_pm" in duty_bcast_cbs
    assert "duty_bcast_dest_groups" in duty_bcast_cbs
    assert "duty_bcast_dest_all" in duty_bcast_cbs
    print("[OK] Duty broadcast destination keyboard (pm, groups, all) verified.")

    # Test Date Schedule Notify keyboard & Substitutions keyboard
    from backend.bot.keyboards.admin_kb import get_date_schedule_notify_keyboard, get_notify_confirm_keyboard
    from backend.bot.services.notifier import escape_md
    dt_kb = get_date_schedule_notify_keyboard()
    dt_cbs = [b.callback_data for row in dt_kb.inline_keyboard for b in row]
    assert "adm_dt_notify_groups" in dt_cbs
    assert "adm_dt_notify_pm" in dt_cbs
    assert "adm_dt_notify_all" in dt_cbs
    assert "adm_dt_notify_no" in dt_cbs

    sub_kb = get_notify_confirm_keyboard()
    sub_cbs = [b.callback_data for row in sub_kb.inline_keyboard for b in row]
    assert "sub_notify_groups" in sub_cbs
    assert "sub_notify_pm" in sub_cbs
    assert "sub_notify_all" in sub_cbs
    assert "sub_notify_no" in sub_cbs

    assert escape_md("mili_") == "mili\\_"
    assert escape_md("test_user_name*") == "test\\_user\\_name\\*"
    print("[OK] Schedule notify keyboards (groups, pm, all, no) and escape_md verification passed.")

    # Test HW notification choice keyboard
    hw_notif_kb = get_hw_notify_keyboard(999)
    hw_notif_cbs = [b.callback_data for row in hw_notif_kb.inline_keyboard for b in row]
    assert "adm_hwnotif_grp_999" in hw_notif_cbs
    assert "adm_hwnotif_all_999" in hw_notif_cbs
    assert "adm_hwnotif_none" in hw_notif_cbs
    assert "adm_hw_del_999" in hw_notif_cbs
    print("[OK] Homework broadcast destination & delete confirmation keyboards verified.")


    from backend.api.auth import get_current_webapp_user
    from backend.db.models import User
    fake_user = User(id=1, tg_id=123456, full_name="Test Student", role="student")
    app.dependency_overrides[get_current_webapp_user] = lambda: fake_user


    client = TestClient(app)

    # Test that /api/homework returns homework for requested calendar date
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    res_hw_yesterday = client.get(f"/api/homework?target_date={yesterday_str}")
    assert res_hw_yesterday.status_code == 200
    assert len(res_hw_yesterday.json()) >= 1, "API must return homework when explicitly requested by date for calendar!"
    print("[OK] /api/homework calendar date retrieval verified.")



    res_health = client.get("/health")
    assert res_health.status_code == 200

    res_app = client.get("/app")
    assert res_app.status_code == 200
    assert "11 «Б»" in res_app.text
    assert "duty-widget" in res_app.text
    assert "daily-fact-widget" in res_app.text

    res_sched = client.get("/api/schedule")
    assert res_sched.status_code == 200
    assert res_sched.json()["class_name"] == "11 «Б»"

    res_duty = client.get("/api/duty")
    assert res_duty.status_code == 200
    duty_data = res_duty.json()
    assert "current_group" in duty_data
    assert "members" in duty_data
    assert len(duty_data["all_groups"]) in [5, 6]
    print("[OK] /api/duty and Mini App duty widget verified.")

    res_fact = client.get("/api/facts/today")
    assert res_fact.status_code == 200
    fact_data = res_fact.json()
    assert "category" in fact_data
    assert "title" in fact_data
    assert "fact" in fact_data
    print("[OK] /api/facts/today endpoint verified.")

    res_bells = client.get("/api/bells")
    assert res_bells.status_code == 200
    assert len(res_bells.json()) == 8
    print("[OK] /api/bells endpoint verified.")


async def main():
    await test_database_and_crud()
    test_keyboards_and_fastapi()
    p2_scripts = (
        "tests/natbirzha/test_p2_models.py",
        "tests/natbirzha/test_p2_migrations.py",
        "tests/natbirzha/test_combat_resolver.py",
        "tests/natbirzha/test_premium_and_licenses.py",
        "tests/natbirzha/test_army_service.py",
        "tests/natbirzha/test_pve_wars.py",
        "tests/natbirzha/test_tournament_lifecycle.py",
        "tests/natbirzha/test_tournament_pvp.py",
        "tests/natbirzha/test_creator_custom_tournaments.py",
        "tests/natbirzha/test_premium_production.py",
        "tests/natbirzha/test_premium_military_upgrades.py",
        "tests/natbirzha/test_p2_backend_api.py",
        "tests/natbirzha/test_reference_instruments.py",
        "tests/natbirzha/test_bond_lifecycle.py",
    )
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = os.path.abspath(".")
    for script in p2_scripts:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=child_env,
        )
        output, _ = await process.communicate()
        rendered = output.decode("utf-8", errors="replace").strip()
        if rendered:
            print(rendered)
        assert process.returncode == 0, f"P2 regression failed: {script}"
    print("\n=== ALL 11 «Б» BOT TESTS PASSED SUCCESSFULLY! ZERO ERRORS! ===\n")

if __name__ == "__main__":
    asyncio.run(main())
