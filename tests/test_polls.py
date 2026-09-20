import asyncio
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_polls.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_polls.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.models import Base, User, GroupChat
from backend.db.crud.polls import (
    create_poll,
    get_poll_by_id,
    get_active_polls,
    close_poll,
    delete_poll,
    record_or_update_vote,
    get_poll_results_data,
    get_poll_non_voters,
    format_poll_message_text,
    generate_progress_bar,
    add_dispatched_message,
)
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard
from backend.bot.handlers.polls import cb_poll_vote, get_poll_voting_keyboard


async def run_polls_test_suite():
    print("=== [1/5] Testing DB Init & Poll Creation ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Seed 3 test users
        u1 = User(tg_id=111, full_name="Иван Иванов", role="student")
        u2 = User(tg_id=222, full_name="Дарина", role="student")
        u3 = User(tg_id=333, full_name="Айгиз", role="student")
        u4 = User(tg_id=999, full_name="Админ", role="admin")
        session.add_all([u1, u2, u3, u4])
        await session.commit()

        # Create poll
        poll = await create_poll(
            session=session,
            question="Переносим репетицию на 16:00?",
            options_texts=["Да, в 16:00", "Нет, в 17:00", "Не смогу"],
            creator_tg_id=999,
            is_anonymous=False,
            allow_revote=True
        )
        assert poll is not None
        assert poll.question == "Переносим репетицию на 16:00?"
        assert len(poll.options) == 3
        assert poll.options[0].option_text == "Да, в 16:00"
        assert poll.options[1].option_text == "Нет, в 17:00"
        assert poll.options[2].option_text == "Не смогу"
        assert poll.is_closed is False
        print(f"[OK] Poll #{poll.id} created with 3 options.")

    print("\n=== [2/5] Testing Voting, Statistics & Revoting ===")
    async with async_session_factory() as session:
        poll = (await get_active_polls(session))[0]
        opt1 = poll.options[0].id
        opt2 = poll.options[1].id

        # User 111 votes for opt1
        success, status, p1 = await record_or_update_vote(session, poll.id, opt1, 111)
        assert success is True and status == "voted"

        # User 222 votes for opt1
        success, status, p2 = await record_or_update_vote(session, poll.id, opt1, 222)
        assert success is True and status == "voted"

        # User 333 votes for opt2
        success, status, p3 = await record_or_update_vote(session, poll.id, opt2, 333)
        assert success is True and status == "voted"

        # Check results
        results = await get_poll_results_data(session, poll.id)
        assert results["total_votes"] == 3
        # opt1: 2 votes (67%)
        assert results["options"][0]["count"] == 2
        assert abs(results["options"][0]["percentage"] - 66.67) < 1.0
        # opt2: 1 vote (33%)
        assert results["options"][1]["count"] == 1
        # Non-anonymous check: voter names listed
        assert "Иван Иванов" in results["options"][0]["voters"]
        assert "Дарина" in results["options"][0]["voters"]
        assert "Айгиз" in results["options"][1]["voters"]
        print("[OK] 3 votes recorded, percentages and voter names verified.")

        # Revote test (User 333 changes vote from opt2 to opt1)
        success_revote, status_revote, p_revote = await record_or_update_vote(session, poll.id, opt1, 333)
        assert success_revote is True and status_revote == "revoted"

        results_after = await get_poll_results_data(session, poll.id)
        assert results_after["options"][0]["count"] == 3
        assert results_after["options"][1]["count"] == 0
        print("[OK] Vote change (revoting) verified.")

    print("\n=== [3/5] Testing Non-Revotable & Anonymous Polls ===")
    async with async_session_factory() as session:
        # Create non-revotable anonymous poll
        poll_strict = await create_poll(
            session=session,
            question="Анонимный строгий опрос",
            options_texts=["Вариант А", "Вариант Б"],
            creator_tg_id=999,
            is_anonymous=True,
            allow_revote=False
        )
        optA = poll_strict.options[0].id
        optB = poll_strict.options[1].id

        # Vote once
        ok, st, _ = await record_or_update_vote(session, poll_strict.id, optA, 111)
        assert ok is True and st == "voted"

        # Try to change vote when allow_revote=False
        ok_fail, st_fail, _ = await record_or_update_vote(session, poll_strict.id, optB, 111)
        assert ok_fail is False and st_fail == "no_revote"
        print("[OK] Non-revotable restriction strictly verified.")

        # Check anonymity
        res_anon = await get_poll_results_data(session, poll_strict.id)
        assert len(res_anon["options"][0]["voters"]) == 0, "Anonymous poll must not expose voter names"
        print("[OK] Anonymity protection verified.")

    print("\n=== [4/5] Testing Non-Voters List & Poll Closure ===")
    async with async_session_factory() as session:
        poll_strict = (await get_active_polls(session))[0]
        # In poll_strict, only 111 has voted. Users 222, 333, 999 are non-voters
        non_voters = await get_poll_non_voters(session, poll_strict.id)
        non_voter_ids = {u.tg_id for u in non_voters}
        assert 111 not in non_voter_ids
        assert 222 in non_voter_ids and 333 in non_voter_ids
        print(f"[OK] Non-voters tracking verified: {len(non_voters)} non-voters found.")

        # Close poll
        closed = await close_poll(session, poll_strict.id)
        assert closed.is_closed is True

        # Try to vote on closed poll
        ok_closed, st_closed, _ = await record_or_update_vote(session, poll_strict.id, optB, 222)
        assert ok_closed is False and st_closed == "closed"
        print("[OK] Closed poll voting prevention verified.")

    print("\n=== [5/5] Testing Keyboard & Callback Routing ===")
    adm_kb = get_admin_panel_keyboard()
    adm_cbs = [b.callback_data for row in adm_kb.inline_keyboard for b in row]
    assert "admin_polls_menu" in adm_cbs, "'admin_polls_menu' button must be in admin panel"
    print("[OK] 'admin_polls_menu' verified in admin panel keyboard.")

    # Test voting keyboard formatting
    async with async_session_factory() as session:
        active_polls = await get_active_polls(session)
        poll = active_polls[0]
        voting_kb = get_poll_voting_keyboard(poll)
        vote_cbs = [b.callback_data for row in voting_kb.inline_keyboard for b in row]
        assert len(vote_cbs) == len(poll.options)
        for opt in poll.options:
            assert f"poll_vote_{poll.id}_{opt.id}" in vote_cbs
        print("[OK] Public poll voting inline buttons format verified.")

    print("\n" + "=" * 60)
    print(">>> ALL CLASS POLL TESTS PASSED FLAWLESSLY! ZERO ERRORS! <<<")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_polls_test_suite())
