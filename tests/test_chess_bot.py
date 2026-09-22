import asyncio
import os
import sys
from fastapi.testclient import TestClient
import chess

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_chess_bot.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.crud import create_user, update_user_role
from backend.api.game_rooms import GameRoomManager, ChessRoom
from backend.api.chess_ai import get_best_bot_move, evaluate_board
from backend.main import app


async def run_bot_tests():
    print("=== [1/3] Testing Chess AI Minimax & Anti-Loop Logic ===")
    board = chess.Board()

    # 1. Opening move search depth 3
    best_move = get_best_bot_move(board, depth=3)
    assert best_move in board.legal_moves, "Best move must be legal"
    print(f"[OK] Minimax depth 3 found valid initial move: {best_move.uci()}")

    # 2. Tactical Mate-in-1 detection
    mate_board = chess.Board("r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1")
    # Scholar's mate: Qxf7#
    mate_move = get_best_bot_move(mate_board, depth=3)
    assert mate_move.uci() == "h5f7", f"Expected h5f7#, got {mate_move.uci()}"
    print("[OK] Minimax depth 3 correctly detects Scholar's Mate-in-1 (h5f7#).")

    # 3. Anti-loop / repetition protection
    # Setup position where repeating move causes 3-fold repetition
    rep_board = chess.Board()
    # Play Nf3 Nf6 Ng1 Ng8 (position repeated once)
    rep_board.push_san("Nf3")
    rep_board.push_san("Nf6")
    rep_board.push_san("Ng1")
    rep_board.push_san("Ng8")
    fen_after = rep_board.fen()

    # Provide position history showing this FEN appeared before
    pos_history = [fen_after, "dummy_fen", fen_after]
    move_with_penalty = get_best_bot_move(rep_board, depth=3, position_history=pos_history)
    assert move_with_penalty in rep_board.legal_moves
    print(f"[OK] Anti-loop move selected under repetition history: {move_with_penalty.uci()}")

    print("\n=== [2/3] Testing ChessRoom Bot Mechanics ===")
    mgr = GameRoomManager()

    # 1. Bot room with player as White
    room_white = mgr.create_bot_room(host_tg_id=1001, host_name="ИгрокБелый", game_type="chess", host_color="white")
    assert isinstance(room_white, ChessRoom)
    assert room_white.is_bot is True
    assert room_white.bot_color == "black"
    assert room_white.status == "playing"
    assert room_white.turn == "white"
    assert room_white.get_player_role(1001) == "white"

    # Player moves e2e4 -> Bot must immediately answer
    ok, msg = mgr.make_move(room_white.room_id, 1001, "e2e4")
    assert ok is True
    assert room_white.turn == "white", "Turn must return to player after instant bot response"
    assert len(room_white.board.move_stack) == 2, f"Move stack should have 2 moves, got {len(room_white.board.move_stack)}"
    bot_reply = room_white.board.move_stack[-1].uci()
    print(f"[OK] Player played e2e4 -> Bot instantly responded with {bot_reply}")

    # 2. Bot room with player as Black (Bot plays White and makes opening move!)
    room_black = mgr.create_bot_room(host_tg_id=1002, host_name="ИгрокЧерный", game_type="chess", host_color="black")
    assert room_black.is_bot is True
    assert room_black.bot_color == "white"
    assert room_black.status == "playing"
    assert room_black.turn == "black", "Turn should be Black since White bot already made opening move"
    assert len(room_black.board.move_stack) == 1, "White bot must have made opening move on creation"
    first_move = room_black.last_move
    assert first_move is not None
    print(f"[OK] Host chose Black -> White bot opened the game with {first_move}")

    # Black player moves
    legal_moves_black = [m.uci() for m in room_black.board.legal_moves]
    player_black_move = "e7e5" if "e7e5" in legal_moves_black else legal_moves_black[0]
    ok, msg = mgr.make_move(room_black.room_id, 1002, player_black_move)
    assert ok is True
    assert room_black.turn == "black"
    assert len(room_black.board.move_stack) == 3, f"Expected 3 moves after bot reply, got {len(room_black.board.move_stack)}"
    print(f"[OK] Black player moved {player_black_move} -> Bot replied instantly")

    # 3. Resignation against Bot
    ok, msg = mgr.resign_room(room_black.room_id, 1002)
    assert ok is True
    assert room_black.status == "finished"
    assert room_black.winner == "white", "Bot was White, so White won on Black's resignation"
    assert room_black.termination_reason == "resignation"
    print("[OK] Resignation against bot verified: winner=white, reason=resignation.")

    # 4. Rematch against Bot (Color swap)
    ok, msg = mgr.request_rematch(room_black.room_id, 1002)
    assert ok is True
    assert room_black.status == "playing"
    # Player was Black, now player must be White!
    assert room_black.get_player_role(1002) == "white"
    assert room_black.bot_color == "black"
    assert room_black.turn == "white"
    print("[OK] Rematch against bot swapped colors: Player is now White, Bot is Black.")

    print("\n=== [3/3] Testing Bot HTTP Endpoints ===")
    async with engine.begin() as conn:
        from backend.db.models import Base
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        await create_user(session, tg_id=888001, full_name="BotChessTester", username="bot_tester")
        await update_user_role(session, 888001, "student")
        await session.commit()

    client = TestClient(app)

    # API 1: Create bot room via POST /api/games/bot
    resp = client.post(
        "/api/games/bot",
        json={"game_type": "chess", "host_color": "white"},
        headers={"X-Telegram-User-Id": "888001"}
    )
    assert resp.status_code == 200, resp.text
    b_data = resp.json()
    assert b_data["status"] == "playing"
    assert b_data["is_bot"] is True
    assert b_data["bot_color"] == "black"
    assert b_data["is_your_turn"] is True
    room_id = b_data["room_id"]
    print(f"[OK] POST /api/games/bot -> room_id={room_id}, status={b_data['status']}")

    # API 2: Player makes move e2e4 via API -> bot replies in same response
    resp = client.post(
        f"/api/games/room/{room_id}/move",
        json={"uci": "e2e4"},
        headers={"X-Telegram-User-Id": "888001"}
    )
    assert resp.status_code == 200
    m_data = resp.json()
    assert m_data["status"] == "playing"
    assert m_data["is_your_turn"] is True
    assert m_data["turn"] == "white"
    print(f"[OK] POST /api/games/room/{room_id}/move executed, bot reply received: {m_data['last_move']}")

    # API 3: Create bot room with host_color="black" -> bot already moved
    resp = client.post(
        "/api/games/bot",
        json={"game_type": "chess", "host_color": "black"},
        headers={"X-Telegram-User-Id": "888001"}
    )
    assert resp.status_code == 200
    blk_data = resp.json()
    assert blk_data["status"] == "playing"
    assert blk_data["is_bot"] is True
    assert blk_data["bot_color"] == "white"
    assert blk_data["your_role"] == "black"
    assert blk_data["is_your_turn"] is True
    assert blk_data["last_move"] is not None
    print(f"[OK] POST /api/games/bot (black) -> Bot made first move: {blk_data['last_move']}")


if __name__ == "__main__":
    asyncio.run(run_bot_tests())
    print("\nALL CHESS BOT TESTS PASSED SUCCESSFULLY! ZERO ERRORS!")
