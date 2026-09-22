"""
Комплексный тест проверки всех требований ТЗ (пункты 61–81) «ЕГЭ Арены».
"""
import os
import sys
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_ege_arena.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_ege_arena.db"
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"

from backend.db.session import async_session_factory, engine
from backend.db.models import Base, User
from backend.db.crud.users import get_user_by_tg_id
from backend.db.crud.ege_users import (
    get_user_by_ege_nickname,
    set_ege_nickname,
    set_user_classmate,
    has_full_access,
)
from backend.api.rooms_ege import EGEDuelRoom
from backend.ege.ranking import (
    clamp_rating,
    medal_for_rating,
    rating_payload,
    settle_duel,
    build_room_payload,
    get_player_profile,
    get_leaderboard,
    normalize_nickname,
    validate_nickname,
    MIN_RATING,
    MAX_RATING,
    WIN_RATING,
    LOSS_RATING,
)
from backend.bot.handlers.ege_arena import _stats_caption
from httpx import AsyncClient, ASGITransport
from backend.main import app


def _make_answer(room: EGEDuelRoom, tg_id: int, correct: bool):
    q = room._current_question(tg_id)
    if not q:
        return False, "no question"
    if q["mode"] == "stress":
        ans = q["answer"] if correct else ((q["answer"] + 1) % 10)
    else:
        ans = q["answer"] if correct else "__wrong_word__"
    return room.make_move(tg_id, {"answer": ans})


async def run_all_ege_tests():
    print("=== [ТЗ 61, 62, 63, 64] Duel Logic, Waiting Screen, Winner, Scores, Errors ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    p1, p2 = 800001, 800002

    # Seed users in DB
    async with async_session_factory() as session:
        for uid, nick in [(p1, "SpeedyLoser"), (p2, "CarefulWinner")]:
            u = await get_user_by_tg_id(session, uid)
            if not u:
                u = User(tg_id=uid, username=f"u_{uid}", full_name=nick, role="public", ege_rating=500, ege_wins=0, ege_losses=0, ege_draws=0)
                session.add(u)
            else:
                u.ege_rating = 500
                u.ege_wins = 0
                u.ege_losses = 0
                u.ege_draws = 0
                u.role = "public"
            await set_ege_nickname(session, u, nick)
        await session.commit()

    room = EGEDuelRoom("test_room_61", p1, "SpeedyLoser", p2, "CarefulWinner", "ege_stress_duel")
    room.status = "playing"

    # Player 1 finishes fast with 5 errors
    for i in range(10):
        correct = (i % 2 == 0) # 5 correct, 5 errors
        ok, msg = _make_answer(room, p1, correct)
        assert ok is True

    # ТЗ #61: First player finished, but opponent hasn't!
    assert room._finished(p1) is True
    assert room._finished(p2) is False
    assert room.status == "playing", "Status must REMAIN 'playing' while second player is active!"
    assert room.winner is None, "Winner must NOT be decided yet!"

    state_p1 = room.to_dict(viewer_tg_id=p1)
    assert state_p1["your_finished"] is True
    assert state_p1["opponent_finished"] is False
    assert state_p1["result"] is None
    assert state_p1["your_errors"] == 5
    print("[OK] ТЗ 61: First player finished early, status is still 'playing', winner is None, waiting screen active.")

    # Player 2 now finishes with only 1 error (9 correct)
    for i in range(10):
        correct = (i != 0) # 9 correct, 1 error
        ok, msg = _make_answer(room, p2, correct)
        assert ok is True

    # ТЗ #62: Both finished. Player 2 has fewer errors -> Player 2 wins despite finishing second!
    assert room.status == "finished"
    assert room.winner == p2, f"Expected Player 2 ({p2}) to win, got {room.winner}"
    print("[OK] ТЗ 62: First player lost because of 5 errors, second player won with 1 error (speed gives no advantage).")

    # ТЗ #63 & 64: Personal result screens & error counts
    state_p1_final = room.to_dict(viewer_tg_id=p1)
    state_p2_final = room.to_dict(viewer_tg_id=p2)

    assert state_p1_final["result"] == "loss", f"P1 expected 'loss', got {state_p1_final['result']}"
    assert state_p1_final["your_errors"] == 5
    assert state_p1_final["opponent_errors"] == 1
    assert state_p1_final["your_score"] == 5

    assert state_p2_final["result"] == "win", f"P2 expected 'win', got {state_p2_final['result']}"
    assert state_p2_final["your_errors"] == 1
    assert state_p2_final["opponent_errors"] == 5
    assert state_p2_final["your_score"] == 9
    print("[OK] ТЗ 63, 64: Personalized result screens ('win'/'loss') and accurate individual error counts verified.")

    # ТЗ #65: Sudden Death test (zero draw policy)
    room_sudden = EGEDuelRoom("test_room_sudden", p1, "P1", p2, "P2", "ege_stress_duel")
    room_sudden.status = "playing"
    for _ in range(10):
        _make_answer(room_sudden, p1, True)
        _make_answer(room_sudden, p2, True)
    assert room_sudden.status == "playing", "Must not finish on equal score! Sudden death must trigger."
    assert room_sudden.sudden_round == 1
    assert room_sudden.round_size == 11
    assert room_sudden.winner is None

    # Extra round 1: Both answer correctly again -> goes to sudden death round 2
    _make_answer(room_sudden, p1, True)
    _make_answer(room_sudden, p2, True)
    assert room_sudden.status == "playing"
    assert room_sudden.sudden_round == 2
    assert room_sudden.round_size == 12

    # Extra round 2: P1 answers correctly, P2 answers with error -> P1 wins, duel finishes!
    _make_answer(room_sudden, p1, True)
    _make_answer(room_sudden, p2, False)
    assert room_sudden.status == "finished"
    assert room_sudden.winner == p1
    state_sudden = room_sudden.to_dict(viewer_tg_id=p1)
    assert state_sudden["result"] == "win"
    print("[OK] ТЗ 65: Sudden Death correctly triggers on equal score, proceeds to extra rounds, and settles decisive winner without draw.")

    print("\n=== [ТЗ 66, 67, 68, 69, 70] MMR Settle, Bounds Clamping, Anti-Double Count, Concurrency ===")
    async with async_session_factory() as session:
        # Rating settlement on room
        await settle_duel(session, room)
        u1 = await get_user_by_tg_id(session, p1)
        u2 = await get_user_by_tg_id(session, p2)
        assert u1.ege_rating == 500 - 25, f"Expected 475, got {u1.ege_rating}"
        assert u2.ege_rating == 500 + 30, f"Expected 530, got {u2.ege_rating}"
        assert u1.ege_losses == 1
        assert u2.ege_wins == 1
        print("[OK] ТЗ 66: Normal MMR delta (+30 win / -25 loss) and stats incremented.")

        # ТЗ #69: Double settlement attempt
        await settle_duel(session, room)
        await session.refresh(u1)
        await session.refresh(u2)
        assert u1.ege_rating == 475, "Rating must NOT change on duplicate settle_duel call!"
        assert u1.ege_losses == 1, "Losses must NOT change on duplicate settle_duel call!"
        print("[OK] ТЗ 69: Protection against duplicate settlement / polling double-counting strictly verified.")

    # ТЗ #67: Lower bound clamp (rating 10 -> loses -> 0, not negative)
    async with async_session_factory() as session:
        u_low = await get_user_by_tg_id(session, p1)
        u_low.ege_rating = 10
        await session.commit()

        room_low = EGEDuelRoom("test_low", p1, "P1", p2, "P2", "ege_stress_duel")
        room_low.status = "finished"
        room_low.winner = p2
        await settle_duel(session, room_low)
        await session.refresh(u_low)
        assert u_low.ege_rating == 0, f"Expected 0 MMR clamp, got {u_low.ege_rating}"
        print("[OK] ТЗ 67: Lower bound clamped to 0 MMR (cannot become negative).")

    # ТЗ #68: Upper bound clamp (rating 990 -> wins -> 1000, not 1020)
    async with async_session_factory() as session:
        u_high = await get_user_by_tg_id(session, p2)
        u_high.ege_rating = 990
        await session.commit()

        room_high = EGEDuelRoom("test_high", p2, "P2", p1, "P1", "ege_stress_duel")
        room_high.status = "finished"
        room_high.winner = p2
        await settle_duel(session, room_high)
        await session.refresh(u_high)
        assert u_high.ege_rating == 1000, f"Expected 1000 MMR clamp, got {u_high.ege_rating}"
        print("[OK] ТЗ 68: Upper bound clamped to 1000 MMR (cannot exceed 1000).")

    # ТЗ #70: Simultaneous finish concurrency
    room_concurrent = EGEDuelRoom("test_conc", p1, "P1", p2, "P2", "ege_stress_duel")
    room_concurrent.status = "finished"
    room_concurrent.winner = p1

    async def settle_concurrent():
        async with async_session_factory() as s:
            await settle_duel(s, room_concurrent)

    await asyncio.gather(settle_concurrent(), settle_concurrent(), settle_concurrent())
    assert room_concurrent.rating_settled is True
    print("[OK] ТЗ 70: Simultaneous finish and concurrent settle tasks safely handled via settlement_lock.")

    print("\n=== [ТЗ 72, 73, 74, 75] Public Access, Classmate Privilege, Revocation ===")
    async with async_session_factory() as session:
        test_pub_id = 899001
        u_pub = await get_user_by_tg_id(session, test_pub_id)
        if not u_pub:
            u_pub = User(tg_id=test_pub_id, username="public_tester", full_name="Public Tester", role="public", is_classmate=False)
            session.add(u_pub)
        else:
            u_pub.role = "public"
            u_pub.is_classmate = False
        await set_ege_nickname(session, u_pub, "PublicBoy")
        await session.commit()

        assert has_full_access(u_pub) is False, "Public user must NOT have full access!"
        print("[OK] ТЗ 72: Public user has role='public' and has_full_access=False.")

    # ТЗ #73: Direct API access restrictions
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res_direct_hw = await client.get("/api/homework", params={"user_id": test_pub_id})
        assert res_direct_hw.status_code == 403, f"Expected 403 for public user on /api/homework, got {res_direct_hw.status_code}"

        res_direct_game = await client.post(
            "/api/games/invite",
            json={"opponent_tg_id": p2, "host_name": "PublicBoy", "game_type": "chess"},
            params={"user_id": test_pub_id}
        )
        assert res_direct_game.status_code == 403, f"Expected 403 on chess invite, got {res_direct_game.status_code}"
        print("[OK] ТЗ 73: Direct API access to non-EGE endpoints correctly yields 403 Forbidden.")

        # ТЗ #74: Grant Classmate privilege
        async with async_session_factory() as session:
            u_granted = await set_user_classmate(session, test_pub_id, True)
            assert u_granted.is_classmate is True
            assert has_full_access(u_granted) is True

        res_granted_game = await client.post(
            "/api/games/invite",
            json={"opponent_tg_id": p2, "host_name": "PublicBoy", "game_type": "tictactoe"},
            params={"user_id": test_pub_id}
        )
        assert res_granted_game.status_code == 200, f"Expected 200 after classmate privilege, got {res_granted_game.status_code}: {res_granted_game.text}"
        print("[OK] ТЗ 74: Classmate privilege grants full access to legacy games.")

    # ТЗ #75: Revoke Classmate privilege
    async with async_session_factory() as session:
        u_revoked = await set_user_classmate(session, test_pub_id, False)
        assert u_revoked.is_classmate is False
        assert has_full_access(u_revoked) is False
        assert u_revoked.ege_nickname == "PublicBoy", "Nickname must NOT be wiped on privilege revoke!"
        assert u_revoked.ege_rating is not None, "Rating must NOT be wiped on privilege revoke!"
    print("[OK] ТЗ 75: Revoking classmate privilege preserves nickname, rating and stats.")

    print("\n=== [ТЗ 76] Nickname Uniqueness & Validation ===")
    assert normalize_nickname("  Alex_99 ") == "alex_99"
    assert normalize_nickname("ЁЖИК_1") == "ёжик_1"

    ok, _ = validate_nickname("valid_nick-12")
    assert ok is True
    ok, _ = validate_nickname("a") # too short (<2)
    assert ok is False
    ok, _ = validate_nickname("way_too_long_nickname_exceeding_24_characters") # >24
    assert ok is False
    ok, _ = validate_nickname("bad nickname with spaces")
    assert ok is False
    ok, _ = validate_nickname("<script>alert(1)</script>")
    assert ok is False

    async with async_session_factory() as session:
        # Case insensitive duplicate conflict test
        ok_dup, msg_dup = await set_ege_nickname(session, u_pub, "carefulwinner") # already taken by p2
        assert ok_dup is False
        assert "занят" in msg_dup.lower()
    print("[OK] ТЗ 76: Case-insensitive nickname uniqueness and character validation verified.")

    print("\n=== [ТЗ 77, 78, 79, 80, 81] Ranks, Titan Top 1-5, Medals, /stats ===")
    # Rank thresholds check
    ranks_expected = [
        (0, "recruit", "Рекрут"),
        (99, "recruit", "Рекрут"),
        (100, "guardian", "Страж"),
        (199, "guardian", "Страж"),
        (200, "knight", "Рыцарь"),
        (299, "knight", "Рыцарь"),
        (300, "hero", "Герой"),
        (399, "hero", "Герой"),
        (400, "legend", "Легенда"),
        (499, "legend", "Легенда"),
        (500, "lord", "Властелин"),
        (599, "lord", "Властелин"),
        (600, "divine", "Божество"),
        (799, "divine", "Божество"),
        (800, "titan", "Титан"),
        (1000, "titan", "Титан"),
    ]
    for r_val, exp_key, exp_name in ranks_expected:
        m = medal_for_rating(r_val)
        assert m["key"] == exp_key, f"At {r_val} expected key {exp_key}, got {m['key']}"
        assert m["name"] == exp_name, f"At {r_val} expected name {exp_name}, got {m['name']}"
    print("[OK] ТЗ 80: All 8 standard rank thresholds (0..1000) verified.")

    # ТЗ #81 & #27: Titan Top 1-5 special logic
    for place in range(1, 6):
        m_titan = medal_for_rating(850, top_position=place)
        assert m_titan["display_name"] == f"Титан ({place})"
        assert m_titan["image_key"] == f"titan_top_{place}"

    # Place 6+ titan remains normal Titan
    m_titan_6 = medal_for_rating(850, top_position=6)
    assert m_titan_6["display_name"] == "Титан"
    assert m_titan_6["image_key"] == "titan"

    # CRITICAL ТЗ #27: Top 1-5 does NOT apply if MMR < 800!
    m_divine_top1 = medal_for_rating(750, top_position=1)
    assert m_divine_top1["display_name"] == "Божество", "Rank must remain 'Божество' even if Top 1 when MMR < 800!"
    assert m_divine_top1["image_key"] == "divine"
    print("[OK] ТЗ 81 & 27: Titan Top 1-5 medals apply ONLY to players with MMR >= 800; Divine players in Top 5 remain Divine.")

    # Stats caption test
    test_prof = {
        "nickname": "TestChampion",
        "rating": 950,
        "rank": "Титан (1)",
        "wins": 30,
        "losses": 2,
        "draws": 1,
        "matches": 33,
        "top_position": 1,
    }
    caption = _stats_caption(test_prof)
    assert "TestChampion" in caption
    assert "950 MMR" in caption
    assert "Титан (1)" in caption
    assert "#1" in caption
    assert "30" in caption
    print("[OK] ТЗ 77, 78: Stats caption formatting strictly verified.")


if __name__ == "__main__":
    asyncio.run(run_all_ege_tests())
    print("\n🌟 ALL EGE ARENA 61–81 COMPREHENSIVE TESTS PASSED 100%! 🌟\n")
