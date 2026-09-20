import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import chess

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_chess_game.db"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.crud import create_user, update_user_role
from backend.api.game_rooms import GameRoomManager, ChessRoom, game_manager
from backend.main import app
from backend.bot.bot import set_current_bot


async def run_all_tests():
    print("=== [1/3] Testing ChessRoom Unit Logic ===")
    mgr = GameRoomManager()

    # 1. Create Chess Room
    room = mgr.create_room(
        host_tg_id=111,
        host_name="Белый Игрок",
        opponent_tg_id=222,
        opponent_name="Черный Игрок",
        game_type="chess"
    )
    assert isinstance(room, ChessRoom)
    assert room.game_type == "chess"
    assert room.status == "waiting"
    assert room.turn == "white"
    assert room.get_player_role(111) == "white"
    assert room.get_player_role(222) == "black"
    assert room.get_player_role(999) is None
    assert room.board.fen() == chess.STARTING_FEN
    print("[OK] Chess room created with correct initial state and roles.")

    # 2. Join Chess Room
    ok, msg = mgr.join_room(room.room_id, 222, "Черный Игрок")
    assert ok is True
    assert room.status == "playing"
    print("[OK] Opponent joined, room status is 'playing'.")

    # 3. Turn enforcement & invalid moves
    ok, msg = mgr.make_move(room.room_id, 222, "e7e5")  # Black tries to move first
    assert ok is False
    assert "Сейчас ход другого игрока" in msg

    ok, msg = mgr.make_move(room.room_id, 999, "e2e4")  # Stranger tries to move
    assert ok is False
    assert "Вы не участник" in msg

    ok, msg = mgr.make_move(room.room_id, 111, "invalid_move")
    assert ok is False
    assert "Некорректный формат" in msg

    ok, msg = mgr.make_move(room.room_id, 111, "e2e5")  # Illegal move for pawn
    assert ok is False
    assert "Недопустимый ход" in msg

    # 4. Valid legal moves: e2e4 then e7e5
    ok, msg = mgr.make_move(room.room_id, 111, "e2e4")
    assert ok is True
    assert room.turn == "black"
    assert len(room.board.move_stack) == 1

    ok, msg = mgr.make_move(room.room_id, 222, "e7e5")
    assert ok is True
    assert room.turn == "white"
    print("[OK] Legal moves executed and turns toggled correctly.")

    # 5. Play to Checkmate (Scholar's Mate)
    # 1. e4 e5 (already played)
    # 2. Qh5 Nc6
    ok, msg = mgr.make_move(room.room_id, 111, "d1h5")
    assert ok is True
    ok, msg = mgr.make_move(room.room_id, 222, "b8c6")
    assert ok is True
    # 3. Bc4 Nf6
    ok, msg = mgr.make_move(room.room_id, 111, "f1c4")
    assert ok is True
    ok, msg = mgr.make_move(room.room_id, 222, "g8f6")
    assert ok is True
    # 4. Qxf7#
    ok, msg = mgr.make_move(room.room_id, 111, "h5f7")
    assert ok is True
    assert room.status == "finished"
    assert room.winner == "white"
    assert room.termination_reason == "checkmate"
    print("[OK] Scholar's Mate checkmate detected: winner=white, status=finished.")

    # 6. Moves after game over rejected
    ok, msg = mgr.make_move(room.room_id, 222, "f8e7")
    assert ok is False
    assert "Игра не активна" in msg

    # 7. Rematch with color swap
    # White (111) requests rematch
    ok, msg = mgr.request_rematch(room.room_id, 111)
    assert ok is True
    assert room.rematch_requested_by == "white"
    assert room.status == "finished"

    # Black (222) accepts rematch
    ok, msg = mgr.request_rematch(room.room_id, 222)
    assert ok is True
    assert room.status == "playing"
    assert room.board.fen() == chess.STARTING_FEN
    # Roles must have swapped: 222 is now white, 111 is now black!
    assert room.white_tg_id == 222
    assert room.black_tg_id == 111
    assert room.turn == "white"
    assert room.get_player_role(222) == "white"
    assert room.get_player_role(111) == "black"
    print("[OK] Rematch accepted: colors and roles successfully swapped (222 is now White).")

    # 8. Resignation
    # 222 (now White) resigns
    ok, msg = mgr.resign_room(room.room_id, 222)
    assert ok is True
    assert room.status == "finished"
    assert room.winner == "black"  # 111 wins by resignation
    assert room.termination_reason == "resignation"
    print("[OK] Resignation verified: winner=black, reason=resignation.")

    # 9. Pawn Promotion and Auto-promotion
    promo_room = mgr.create_room(333, "P1", 444, "P2", game_type="chess")
    mgr.join_room(promo_room.room_id, 444, "P2")
    # Set up board with white pawn at a7
    promo_room.board = chess.Board("8/P7/8/8/8/8/8/k6K w - - 0 1")
    # Move a7a8 without promotion suffix should auto-promote to Queen (a7a8q)
    ok, msg = mgr.make_move(promo_room.room_id, 333, "a7a8")
    assert ok is True
    piece = promo_room.board.piece_at(chess.A8)
    assert piece is not None and piece.piece_type == chess.QUEEN
    print("[OK] Pawn auto-promotion to Queen verified.")

    # 10. Color choice: Black for Host
    room_black = mgr.create_room(101, "ХостЧерный", 102, "ОппонентБелый", game_type="chess", host_color="black")
    assert room_black.host_color == "black"
    assert room_black.get_player_role(101) == "black"
    assert room_black.get_player_role(102) == "white"
    assert room_black.white_tg_id == 102
    assert room_black.black_tg_id == 101

    ok, _ = mgr.join_room(room_black.room_id, 102, "ОппонентБелый")
    assert ok is True
    assert room_black.turn == "white"  # White starts!

    # Host (Black) cannot move first
    ok, msg = mgr.make_move(room_black.room_id, 101, "e7e5")
    assert ok is False
    assert "Сейчас ход другого игрока" in msg

    # Opponent (White) moves first
    ok, _ = mgr.make_move(room_black.room_id, 102, "e2e4")
    assert ok is True
    assert room_black.turn == "black"

    # Host (Black) replies
    ok, _ = mgr.make_move(room_black.room_id, 101, "e7e5")
    assert ok is True
    print("[OK] host_color='black' verified: Opponent plays White and moves first, Host plays Black.")

    # 11. Color choice: Random
    room_rnd = mgr.create_room(201, "ХостРанд", 202, "ОппРанд", game_type="chess", host_color="random")
    assert room_rnd.host_color in ["white", "black"]
    assert room_rnd.color_choice_mode == "random"
    assert room_rnd.white_tg_id in [201, 202]
    assert room_rnd.black_tg_id in [201, 202]
    print("[OK] host_color='random' verified: Assigned to either White or Black.")

    print("\n=== [2/3] Testing Captured Pieces Logic ===")
    cap_room = mgr.create_room(555, "W", 666, "B", game_type="chess")
    mgr.join_room(cap_room.room_id, 666, "B")
    # e4 d5, exd5 (White captures black pawn)
    mgr.make_move(cap_room.room_id, 555, "e2e4")
    mgr.make_move(cap_room.room_id, 666, "d7d5")
    mgr.make_move(cap_room.room_id, 555, "e4d5")
    captured = cap_room.get_captured_pieces()
    assert "p" in captured["by_white"]
    assert len(captured["by_black"]) == 0
    print("[OK] Captured pieces tracking verified.")

    print("\n=== [3/3] Testing API Endpoints for Chess ===")
    async with engine.begin() as conn:
        from backend.db.models import Base
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        u1 = await create_user(session, tg_id=777001, full_name="Шахматист1", username="chess_player_1")
        await update_user_role(session, 777001, "student")
        u2 = await create_user(session, tg_id=777002, full_name="Шахматист2", username="chess_player_2")
        await update_user_role(session, 777002, "student")
        await session.commit()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    set_current_bot(mock_bot)

    client = TestClient(app)

    # API 1: Invite opponent with game_type="chess"
    resp = client.post(
        "/api/games/invite",
        json={"opponent_tg_id": 777002, "game_type": "chess"},
        headers={"X-Telegram-User-Id": "777001"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "waiting"
    assert data["game_type"] == "chess"
    room_id = data["room_id"]
    print(f"[OK] POST /api/games/invite (chess) -> room_id={room_id}")

    # Check that bot message contained chess emoji and link
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args.kwargs
    assert "\u0428\u0430\u0445\u043c\u0430\u0442" in call_kwargs["text"]
    assert "game=chess" in str(call_kwargs["reply_markup"])
    print("[OK] Telegram invitation message correctly formatted for Chess.")

    # API 1b: Invite opponent with game_type="chess" and host_color="black"
    resp = client.post(
        "/api/games/invite",
        json={"opponent_tg_id": 777002, "game_type": "chess", "host_color": "black"},
        headers={"X-Telegram-User-Id": "777001"}
    )
    assert resp.status_code == 200
    b_data = resp.json()
    assert b_data["host_color"] == "black"
    assert b_data["host"]["role"] == "black"
    assert b_data["white"]["tg_id"] == 777002
    assert b_data["black"]["tg_id"] == 777001
    print("[OK] POST /api/games/invite with host_color='black' verified via API.")

    # API 2: Get room state as host
    resp = client.get(f"/api/games/room/{room_id}", headers={"X-Telegram-User-Id": "777001"})
    assert resp.status_code == 200
    r_data = resp.json()
    assert r_data["game_type"] == "chess"
    assert r_data["your_role"] == "white"
    assert r_data["is_your_turn"] is False  # Still waiting for opponent to join
    assert "fen" in r_data
    assert "legal_moves" in r_data

    # API 3: Opponent joins
    resp = client.post(f"/api/games/room/{room_id}/join", headers={"X-Telegram-User-Id": "777002"})
    assert resp.status_code == 200
    r_data = resp.json()
    assert r_data["status"] == "playing"
    assert r_data["your_role"] == "black"
    assert r_data["is_your_turn"] is False  # Turn is white

    # API 4: Host plays move e2e4
    resp = client.post(
        f"/api/games/room/{room_id}/move",
        json={"uci": "e2e4"},
        headers={"X-Telegram-User-Id": "777001"}
    )
    assert resp.status_code == 200
    r_data = resp.json()
    assert r_data["last_move"] == "e2e4"
    assert r_data["turn"] == "black"

    # API 5: Opponent resigns
    resp = client.post(f"/api/games/room/{room_id}/resign", headers={"X-Telegram-User-Id": "777002"})
    assert resp.status_code == 200
    r_data = resp.json()
    assert r_data["status"] == "finished"
    assert r_data["winner"] == "white"
    assert r_data["termination_reason"] == "resignation"
    print("[OK] Resign endpoint verified via API.")

    # API 6: Rematch via API
    resp = client.post(f"/api/games/room/{room_id}/rematch", headers={"X-Telegram-User-Id": "777001"})
    assert resp.status_code == 200
    resp = client.post(f"/api/games/room/{room_id}/rematch", headers={"X-Telegram-User-Id": "777002"})
    assert resp.status_code == 200
    r_data = resp.json()
    assert r_data["status"] == "playing"
    assert r_data["white"]["tg_id"] == 777002
    assert r_data["black"]["tg_id"] == 777001
    print("[OK] Rematch endpoint verified via API.")

    # API 7: Cancel room (clean up)
    cancel_room = game_manager.create_room(901, "A", 902, "B", game_type="chess")
    resp = client.post(f"/api/games/room/{cancel_room.room_id}/cancel", headers={"X-Telegram-User-Id": "901"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"
    assert game_manager.get_room(cancel_room.room_id).status == "canceled"
    print("[OK] Cancel endpoint verified for chess room.")

    # API 8: Bot reject callback test
    from backend.bot.handlers.start import callback_game_reject
    reject_room = game_manager.create_room(901, "A", 902, "B", game_type="chess")
    mock_call = MagicMock()
    mock_call.from_user.id = 902
    mock_call.data = f"game_reject:{reject_room.room_id}"
    mock_call.message.edit_text = AsyncMock()
    mock_call.answer = AsyncMock()

    await callback_game_reject(mock_call)
    assert reject_room.status == "rejected"
    assert mock_call.message.edit_text.called
    reject_args = mock_call.message.edit_text.call_args[0][0]
    assert "\u0428\u0430\u0445\u043c\u0430\u0442" in reject_args
    print("[OK] callback_game_reject verified for chess room.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
    print("\nALL CHESS TESTS PASSED SUCCESSFULLY!")
