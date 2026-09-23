# tests/test_checkers_bot.py
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_checkers_bot.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_checkers_bot.db"
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.crud import create_user, update_user_role
from backend.api.rooms_checkers.engine import CheckersBoard
from backend.api.rooms_checkers.ai import get_best_checkers_move, evaluate_board
from backend.api.rooms_checkers.room import CheckersRoom
from backend.api.game_rooms import game_manager
from backend.main import app



async def run_all_tests():
    print("=== [1/3] Testing Checkers Engine & AI ===")
    board = CheckersBoard()
    clone = board.clone()
    assert clone.turn == board.turn
    assert clone.board == board.board

    board.board[5][0] = None
    assert clone.board[5][0] == 'w'
    print("[OK] CheckersBoard.clone() verified.")

    score_w = evaluate_board(board, "white")
    score_b = evaluate_board(board, "black")
    assert score_w == -score_b

    best_move = get_best_checkers_move(board, depth=2, bot_color="white")
    assert best_move in board.get_legal_moves()
    print("[OK] Checkers AI evaluation and best move search verified.")

    print("=== [2/3] Testing CheckersRoom Bot Logic ===")
    # 1. Host as White, Bot as Black
    room = CheckersRoom(
        room_id="test_bot_black",
        host_tg_id=101,
        host_name="Alice",
        host_color="white",
        is_bot=True
    )
    assert room.is_bot is True
    assert room.status == "playing"
    assert room.turn == "white"
    assert room.bot_color == "black"

    legal = room.board.get_legal_moves()
    assert len(legal) > 0
    move = legal[0]

    ok, msg = room.make_move(101, move)
    assert ok is True
    # Bot responded immediately, so it's White's turn again!
    assert room.turn == "white"
    assert len(room.board.move_history) >= 2
    print("[OK] Checkers bot as Black responds immediately to player moves.")

    # 2. Host as Black, Bot as White
    room_white = CheckersRoom(
        room_id="test_bot_white",
        host_tg_id=102,
        host_name="Bob",
        host_color="black",
        is_bot=True
    )
    assert room_white.is_bot is True
    assert room_white.status == "playing"
    assert room_white.bot_color == "white"
    # Bot already made its opening move!
    assert room_white.turn == "black"
    assert len(room_white.board.move_history) >= 1
    print("[OK] Checkers bot as White makes opening move immediately.")

    # 3. Resign & Rematch
    ok, msg = room.resign(101)
    assert ok is True
    assert room.status == "finished"
    assert room.winner == "black"

    ok, msg = room.request_rematch(101)
    assert ok is True
    assert room.status == "playing"
    assert room.host_color == "black"
    assert room.bot_color == "white"
    assert room.turn == "black"
    print("[OK] Checkers bot resign and rematch verified.")

    print("=== [3/3] Testing POST /api/games/bot Endpoint ===")
    from backend.db.models import Base
    from backend.db.crud import get_user_by_tg_id
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        u = await get_user_by_tg_id(session, 888)
        if not u:
            u = await create_user(session, tg_id=888, username="bot_tester", full_name="Tester")
        await update_user_role(session, 888, "student")
        await session.commit()

    client = TestClient(app)

    resp = client.post(
        "/api/games/bot",
        json={"game_type": "checkers", "host_color": "white"},
        headers={"X-Telegram-User-Id": "888"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["game_type"] == "checkers"
    assert data["is_bot"] is True
    assert data["status"] == "playing"
    assert "🤖" in data["opponent"]["name"]
    print("[OK] POST /api/games/bot for checkers verified.")

    # Chess bot via same endpoint
    resp_chess = client.post(
        "/api/games/bot",
        json={"game_type": "chess", "host_color": "black"},
        headers={"X-Telegram-User-Id": "888"}
    )
    assert resp_chess.status_code == 200
    data_chess = resp_chess.json()
    assert data_chess["game_type"] == "chess"
    assert data_chess["is_bot"] is True
    assert data_chess["status"] == "playing"
    print("[OK] POST /api/games/bot for chess verified.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
    print("\nALL CHECKERS BOT TESTS PASSED SUCCESSFULLY!")
