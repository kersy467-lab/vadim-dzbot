import asyncio
import os
import sys
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_online_game.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.crud import create_user, update_user_role
from backend.api.game_rooms import GameRoomManager, TicTacToeRoom, game_manager
from backend.main import app
from backend.bot.bot import set_current_bot

async def run_all_tests():
    print("=== [1/3] Testing GameRoomManager and TicTacToeRoom Logic ===")
    mgr = GameRoomManager()
    
    # 1. Create room
    room = mgr.create_room(host_tg_id=111, host_name="Иван", opponent_tg_id=222, opponent_name="Петр")
    assert room.status == "waiting"
    assert room.turn == "X"
    assert room.board == [""] * 9
    assert room.get_player_role(111) == "X"
    assert room.get_player_role(222) == "O"
    assert room.get_player_role(999) is None
    print("[OK] Room created successfully with correct roles and initial state.")

    # 2. Join room
    ok, msg = mgr.join_room(room.room_id, 222, "Петр")
    assert ok is True
    assert room.status == "playing"
    print("[OK] Opponent joined room, status changed to 'playing'.")

    # 3. Invalid moves
    ok, msg = mgr.make_move(room.room_id, 222, 0)  # O tries to move first, but turn is X
    assert ok is False
    assert "Сейчас ход другого игрока" in msg

    ok, msg = mgr.make_move(room.room_id, 999, 0)  # Stranger tries to move
    assert ok is False
    assert "Вы не участник" in msg

    # 4. Valid moves
    ok, msg = mgr.make_move(room.room_id, 111, 0)  # X moves cell 0
    assert ok is True
    assert room.board[0] == "X"
    assert room.turn == "O"

    ok, msg = mgr.make_move(room.room_id, 111, 1)  # X tries to move again
    assert ok is False

    ok, msg = mgr.make_move(room.room_id, 222, 0)  # O tries occupied cell
    assert ok is False
    assert "Клетка уже занята" in msg

    ok, msg = mgr.make_move(room.room_id, 222, 4)  # O moves center (cell 4)
    assert ok is True
    assert room.board[4] == "O"
    assert room.turn == "X"

    # 5. Play to win: X takes 1, O takes 3, X takes 2 -> X wins top row (0, 1, 2)
    mgr.make_move(room.room_id, 111, 1)
    mgr.make_move(room.room_id, 222, 3)
    ok, msg = mgr.make_move(room.room_id, 111, 2)
    assert ok is True
    assert room.status == "finished"
    assert room.winner == "X"
    print("[OK] Win detection verified (winner = X, status = finished).")

    # Moves forbidden after finish
    ok, msg = mgr.make_move(room.room_id, 222, 8)
    assert ok is False

    # 6. Rematch workflow
    ok, msg = mgr.request_rematch(room.room_id, 111)  # X asks
    assert ok is True
    assert room.rematch_requested_by == "X"
    assert room.status == "finished"

    ok, msg = mgr.request_rematch(room.room_id, 222)  # O accepts!
    assert ok is True
    assert room.status == "playing"
    assert room.board == [""] * 9
    assert room.turn == "X"
    assert room.winner is None
    assert room.rematch_requested_by is None
    print("[OK] Rematch negotiation verified (board reset, status = playing).")

    # 7. Draw scenario
    draw_room = mgr.create_room(10, "A", 20, "B")
    mgr.join_room(draw_room.room_id, 20, "B")
    moves = [
        (10, 0), (20, 1), (10, 2),
        (20, 5), (10, 3), (20, 6),
        (10, 4), (20, 8), (10, 7)
    ]
    for uid, cell in moves:
        ok, _ = mgr.make_move(draw_room.room_id, uid, cell)
        assert ok is True
    assert draw_room.status == "finished"
    assert draw_room.winner == "draw"
    print("[OK] Draw detection verified.")

    # 8. Rejection and Cancellation
    cancel_room = mgr.create_room(10, "A", 20, "B")
    mgr.cancel_room(cancel_room.room_id, 10)
    assert cancel_room.status == "canceled"

    reject_room = mgr.create_room(10, "A", 20, "B")
    mgr.reject_room(reject_room.room_id, 20)
    assert reject_room.status == "rejected"
    print("[OK] Cancellation and rejection verified.")

    print("\n=== [2/3] Testing FastAPI Multiplayer Endpoints ===")
    async with engine.begin() as conn:
        from backend.db.models import Base
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        u1 = await create_user(session, tg_id=5001, username="alex", full_name="Алексей Смирнов")
        await update_user_role(session, 5001, "student")
        u2 = await create_user(session, tg_id=5002, username="daria", full_name="Дарья Иванова")
        await update_user_role(session, 5002, "student")
        await session.commit()

    # Mock bot to capture invitation telegram messages
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    set_current_bot(mock_bot)

    client = TestClient(app)

    # 1. GET /api/games/classmates
    res = client.get("/api/games/classmates?tg_user_id=5001")
    assert res.status_code == 200
    classmates = res.json()
    assert len(classmates) >= 1
    assert any(c["tg_id"] == 5002 for c in classmates)
    print(f"[OK] GET /api/games/classmates returned {len(classmates)} classmate(s).")

    # 2. POST /api/games/invite
    res = client.post(
        "/api/games/invite",
        json={"opponent_tg_id": 5002, "host_name": "Алексей Смирнов"},
        headers={"X-Telegram-User-Id": "5001"}
    )
    assert res.status_code == 200
    room_data = res.json()
    room_id = room_data["room_id"]
    assert room_data["status"] == "waiting"
    assert room_data["host"]["tg_id"] == 5001
    assert room_data["opponent"]["tg_id"] == 5002
    assert room_data["bot_notified"] is True
    assert mock_bot.send_message.called
    print(f"[OK] POST /api/games/invite created room {room_id} and notified opponent via Bot.")

    # 3. GET /api/games/room/{room_id}
    res = client.get(f"/api/games/room/{room_id}?tg_user_id=5001")
    assert res.status_code == 200
    state = res.json()
    assert state["status"] == "waiting"
    assert state["your_role"] == "X"
    print("[OK] GET /api/games/room/{room_id} verified.")

    # 4. POST /api/games/room/{room_id}/join
    res = client.post(
        f"/api/games/room/{room_id}/join",
        json={"user_name": "Дарья Иванова"},
        headers={"X-Telegram-User-Id": "5002"}
    )
    assert res.status_code == 200
    state = res.json()
    assert state["status"] == "playing"
    assert state["your_role"] == "O"
    assert state["is_your_turn"] is False  # X moves first
    print("[OK] POST /api/games/room/{room_id}/join connected opponent.")

    # 5. POST /api/games/room/{room_id}/move
    res = client.post(
        f"/api/games/room/{room_id}/move",
        json={"cell": 4},
        headers={"X-Telegram-User-Id": "5001"}
    )
    assert res.status_code == 200
    state = res.json()
    assert state["board"][4] == "X"
    assert state["turn"] == "O"
    assert state["is_your_turn"] is False  # now O's turn

    # Opponent makes move
    res = client.post(
        f"/api/games/room/{room_id}/move",
        json={"cell": 0},
        headers={"X-Telegram-User-Id": "5002"}
    )
    assert res.status_code == 200
    state = res.json()
    assert state["board"][0] == "O"
    assert state["turn"] == "X"
    print("[OK] POST /api/games/room/{room_id}/move verified for both players.")

    # 6. Rematch and Cancel
    # Finish game quickly
    client.post(f"/api/games/room/{room_id}/move", json={"cell": 3}, headers={"X-Telegram-User-Id": "5001"})
    client.post(f"/api/games/room/{room_id}/move", json={"cell": 1}, headers={"X-Telegram-User-Id": "5002"})
    res = client.post(f"/api/games/room/{room_id}/move", json={"cell": 5}, headers={"X-Telegram-User-Id": "5001"})
    state = res.json()
    assert state["status"] == "finished"
    assert state["winner"] == "X"

    # Rematch request
    res = client.post(f"/api/games/room/{room_id}/rematch", headers={"X-Telegram-User-Id": "5001"})
    assert res.status_code == 200
    assert res.json()["rematch_requested_by"] == "X"

    # Rematch accept
    res = client.post(f"/api/games/room/{room_id}/rematch", headers={"X-Telegram-User-Id": "5002"})
    assert res.status_code == 200
    assert res.json()["status"] == "playing"
    print("[OK] Rematch endpoint cycle completed successfully.")

    # Cancel test
    res = client.post(f"/api/games/room/{room_id}/cancel", headers={"X-Telegram-User-Id": "5001"})
    assert res.status_code == 200
    assert res.json()["status"] == "canceled"
    print("[OK] Cancel endpoint verified.")

    print("\n=== [3/3] Testing Bot Reject Callback ===")
    from backend.bot.handlers.start import callback_game_reject
    test_room = game_manager.create_room(5001, "Алексей", 5002, "Дарья")
    
    mock_call = MagicMock()
    mock_call.from_user.id = 5002
    mock_call.data = f"game_reject:{test_room.room_id}"
    mock_call.message.edit_text = AsyncMock()
    mock_call.answer = AsyncMock()

    await callback_game_reject(mock_call)
    assert test_room.status == "rejected"
    assert mock_call.message.edit_text.called
    print("[OK] callback_game_reject correctly rejected room and updated message.")

    print("\n[SUCCESS] ALL ONLINE MULTIPLAYER TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
