# tests/test_checkers_game.py
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_checkers_game.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.crud import create_user, update_user_role
from backend.api.rooms_checkers import CheckersBoard, CheckersRoom
from backend.api.game_rooms import GameRoomManager, game_manager
from backend.main import app
from backend.bot.bot import set_current_bot

async def run_all_tests():
    print("=== [1/3] Testing CheckersBoard Engine Logic ===")
    b = CheckersBoard()
    # 1. Initial setup
    assert len(b.get_legal_moves()) == 7  # 7 opening quiet moves for white (e.g. a3b4, c3b4, c3d4, e3d4, e3f4, g3f4, g3h4)
    assert b.turn == "white"
    assert b.active_jump_piece is None

    # 2. Quiet move
    ok, msg = b.push_move("c3d4")
    assert ok is True
    assert b.turn == "black"
    assert b.board[5][2] is None  # c3 empty
    assert b.board[4][3] == 'w'   # d4 has white piece

    # 3. Black quiet move: b6c5 (leaves b6 empty!)
    ok, msg = b.push_move("b6c5")
    assert ok is True
    assert b.turn == "white"

    # 4. Mandatory capture: white piece at d4 MUST jump over c5 to b6!
    # Quiet move e3f4 should be rejected because capture is available
    ok, msg = b.push_move("e3f4")
    assert ok is False
    assert "Взятие обязательно" in msg

    # Execute mandatory capture: d4b6
    ok, msg = b.push_move("d4b6")
    assert ok is True
    assert b.turn == "black"
    assert b.board[3][2] is None  # c5 captured and removed
    assert b.board[2][1] == 'w'   # landed on b6

    # 5. Backward capture for simple piece test
    b2 = CheckersBoard()
    b2.load_fen("......../......../......../....b.../.....w../......../......../........ w -")
    # White piece at f4 (r=4, c=5), Black piece at e5 (r=3, c=4).
    # White at f4 can jump backward or forward? Let's place black piece behind white:
    b2.load_fen("......../......../......../......../.....w../....b.../......../........ w -")
    # White at f4 (r=4, c=5), Black at e3 (r=5, c=4). Jump over e3 lands on d2 (r=6, c=3).
    # This is a backward jump for white!
    caps = b2.get_piece_captures(4, 5)
    assert len(caps) == 1
    landing, mid = caps[0]
    assert b2.rc_to_sq(*landing) == "d2"
    assert b2.rc_to_sq(*mid) == "e3"
    ok, _ = b2.push_move("f4d2")
    assert ok is True
    assert b2.board[5][4] is None  # e3 captured!
    print("[OK] Simple piece backward capture verified.")

    # 6. Flying king movement & capture test
    b_king = CheckersBoard()
    # White king at a1 (r=7, c=0), Black piece at c3 (r=5, c=2), empty diagonal up to h8
    b_king.load_fen("......../......../......../......../......../..b...../......../W....... w -")
    king_caps = b_king.get_piece_captures(7, 0)
    # Landing squares: d4, e5, f6, g7, h8 (5 squares!)
    landing_squares = [b_king.rc_to_sq(*pos) for pos, _ in king_caps]
    assert "d4" in landing_squares and "h8" in landing_squares
    assert len(landing_squares) == 5

    ok, _ = b_king.push_move("a1f6")
    assert ok is True
    assert b_king.board[5][2] is None  # c3 captured
    assert b_king.board[2][5] == 'W'   # landed on f6
    print("[OK] Flying king multiple landing squares verified.")

    # 7. Multi-jump test
    b_multi = CheckersBoard()
    # White at c3 (r=5, c=2), Black at d4 (r=4, c=3) and f6 (r=2, c=5)
    b_multi.load_fen("......../......../.....b../......../...b..../..w...../......../........ w -")
    ok, res = b_multi.push_move("c3e5g7")
    assert ok is True
    assert b_multi.board[4][3] is None  # d4 captured
    assert b_multi.board[2][5] is None  # f6 captured
    assert b_multi.board[1][6] == 'w'   # landed on g7
    assert b_multi.turn == "black"
    print("[OK] Multi-jump chain verified.")

    print("\n=== [2/3] Testing CheckersRoom Logic ===")
    mgr = GameRoomManager()
    # 1. Online Room
    room = mgr.create_room(111, "Белый", 222, "Черный", game_type="checkers")
    assert isinstance(room, CheckersRoom)
    assert room.status == "waiting"
    assert room.get_player_role(111) == "white"
    assert room.get_player_role(222) == "black"

    ok, _ = mgr.join_room(room.room_id, 222, "Черный")
    assert ok is True
    assert room.status == "playing"

    # White moves
    ok, _ = mgr.make_move(room.room_id, 111, "c3d4")
    assert ok is True
    assert room.turn == "black"

    # Resign
    ok, _ = mgr.resign_room(room.room_id, 222)
    assert ok is True
    assert room.status == "finished"
    assert room.winner == "white"
    assert room.termination_reason == "resignation"

    # Rematch with color swap
    mgr.request_rematch(room.room_id, 111)
    mgr.request_rematch(room.room_id, 222)
    assert room.status == "playing"
    assert room.white_tg_id == 222  # Colors swapped!
    assert room.black_tg_id == 111
    print("[OK] Online room, resignation, and rematch color swap verified.")

    # 2. Local 2-players on 1 phone
    local_room = mgr.create_local_room(333, "Хост", game_type="checkers")
    assert local_room.is_local is True
    assert local_room.status == "playing"
    assert local_room.turn == "white"
    # Make move in local room
    ok, _ = mgr.make_move(local_room.room_id, 333, "c3d4")
    assert ok is True
    assert local_room.turn == "black"
    print("[OK] Local 2-players on 1 phone verified.")

    print("\n=== [3/3] Testing Checkers API Endpoints ===")
    async with engine.begin() as conn:
        from backend.db.models import Base
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await create_user(session, tg_id=888001, full_name="Шашист1", username="checkers_1")
        await update_user_role(session, 888001, "student")
        await create_user(session, tg_id=888002, full_name="Шашист2", username="checkers_2")
        await update_user_role(session, 888002, "student")
        await session.commit()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    set_current_bot(mock_bot)
    client = TestClient(app)

    # API 1: Local game creation
    resp = client.post("/api/games/local", json={"game_type": "checkers"}, headers={"X-Telegram-User-Id": "888001"})
    assert resp.status_code == 200
    assert resp.json()["game_type"] == "checkers"
    assert resp.json()["is_local"] is True
    print("[OK] POST /api/games/local (checkers) succeeded.")

    # API 2: Invite opponent
    resp = client.post(
        "/api/games/invite",
        json={"opponent_tg_id": 888002, "game_type": "checkers"},
        headers={"X-Telegram-User-Id": "888001"}
    )
    assert resp.status_code == 200
    c_data = resp.json()
    assert c_data["game_type"] == "checkers"
    assert c_data["status"] == "waiting"
    r_id = c_data["room_id"]

    # Verify bot message
    mock_bot.send_message.assert_called()
    call_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "Шашки" in call_text
    print("[OK] POST /api/games/invite (checkers) notification sent.")

    # API 3: Opponent joins
    resp = client.post(f"/api/games/room/{r_id}/join", headers={"X-Telegram-User-Id": "888002"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "playing"

    # API 4: Move
    resp = client.post(f"/api/games/room/{r_id}/move", json={"move": "c3d4"}, headers={"X-Telegram-User-Id": "888001"})
    assert resp.status_code == 200
    assert resp.json()["turn"] == "black"
    print("[OK] Move via API succeeded.")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
    print("\nALL CHECKERS TESTS PASSED SUCCESSFULLY!")
