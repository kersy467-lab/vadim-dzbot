# tests/test_invite_cancellation.py
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_invite_cancel.db"
os.environ["BOT_TOKEN"] = "1234567890:ABCdefFakeTestToken"

from backend.config import settings
settings.DATABASE_URL = "sqlite+aiosqlite:///./data/test_invite_cancel.db"
settings.BOT_TOKEN = "1234567890:ABCdefFakeTestToken"

from backend.db.session import init_db, async_session_factory, engine
from backend.db.models import Base
from backend.db.crud import create_user, update_user_role, get_user_by_tg_id
from backend.api.game_rooms import game_manager
from backend.api.routers.games_rpg_hooks import (
    send_game_invite_notification,
    update_canceled_invite_message,
)
from backend.main import app


async def run_all_tests():
    print("=== [1/3] Testing send_game_invite_notification & update_canceled_invite_message ===")
    mock_bot = MagicMock()
    mock_sent_msg = MagicMock()
    mock_sent_msg.message_id = 9988
    mock_bot.send_message = AsyncMock(return_value=mock_sent_msg)
    mock_bot.edit_message_text = AsyncMock(return_value=True)

    # 1. Checkers room
    room = game_manager.create_room(
        host_tg_id=501,
        host_name="Иван",
        opponent_tg_id=502,
        opponent_name="Пётр",
        game_type="checkers"
    )

    await send_game_invite_notification(
        bot=mock_bot,
        opponent_tg_id=502,
        invite_text="Вызов в шашки",
        reply_markup=None,
        room=room
    )
    assert room.invite_msg_id == 9988
    assert room.invite_chat_id == 502
    print("[OK] send_game_invite_notification saved invite_msg_id and invite_chat_id on room.")

    ok = await update_canceled_invite_message(mock_bot, room)
    assert ok is True
    mock_bot.edit_message_text.assert_called_once()
    call_kwargs = mock_bot.edit_message_text.call_args[1]
    assert call_kwargs["chat_id"] == 502
    assert call_kwargs["message_id"] == 9988
    assert "Шашки" in call_kwargs["text"]
    assert "Иван" in call_kwargs["text"]
    assert call_kwargs["reply_markup"] is None
    print("[OK] update_canceled_invite_message successfully edited message removing buttons.")

    print("=== [2/3] Testing Cancel via API endpoint ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        for uid in (601, 701):
            u = await get_user_by_tg_id(session, uid)
            if not u:
                u = await create_user(session, tg_id=uid, username=f"user_{uid}", full_name=f"User {uid}")
            await update_user_role(session, uid, "student")
        await session.commit()

    from backend.bot.bot import set_current_bot, get_current_bot
    orig_bot = get_current_bot()
    set_current_bot(mock_bot)
    client = TestClient(app)

    try:
        mock_bot.edit_message_text.reset_mock()

        # Create Chess Room & Cancel
        chess_room = game_manager.create_room(
            host_tg_id=601,
            host_name="Алексей",
            opponent_tg_id=602,
            opponent_name="Сергей",
            game_type="chess"
        )
        chess_room.invite_msg_id = 1234
        chess_room.invite_chat_id = 602

        resp = client.post(
            f"/api/games/room/{chess_room.room_id}/cancel",
            headers={"X-Telegram-User-Id": "601"}
        )
        assert resp.status_code == 200, resp.text
        assert chess_room.status == "canceled"

        mock_bot.edit_message_text.assert_called_once()
        call_kwargs = mock_bot.edit_message_text.call_args[1]
        assert call_kwargs["chat_id"] == 602
        assert call_kwargs["message_id"] == 1234
        assert "Шахматы" in call_kwargs["text"]
        assert "Алексей" in call_kwargs["text"]
        assert call_kwargs["reply_markup"] is None
        print("[OK] Cancel chess room via API updated Telegram message.")

        mock_bot.edit_message_text.reset_mock()

        # Create EGE Duel Room & Cancel
        ege_room = game_manager.create_room(
            host_tg_id=701,
            host_name="Мария",
            opponent_tg_id=702,
            opponent_name="Ольга",
            game_type="ege_stress_duel"
        )
        ege_room.invite_msg_id = 5678
        ege_room.invite_chat_id = 702

        resp_ege = client.post(
            f"/api/games/room/{ege_room.room_id}/cancel",
            headers={"X-Telegram-User-Id": "701"}
        )
        assert resp_ege.status_code == 200, resp_ege.text
        assert ege_room.status == "canceled"

        mock_bot.edit_message_text.assert_called_once()
        call_kwargs_ege = mock_bot.edit_message_text.call_args[1]
        assert call_kwargs_ege["chat_id"] == 702
        assert call_kwargs_ege["message_id"] == 5678
        assert "ЕГЭ-дуэль" in call_kwargs_ege["text"]
        assert "Мария" in call_kwargs_ege["text"]
        assert call_kwargs_ege["reply_markup"] is None
        print("[OK] Cancel EGE duel room via API updated Telegram message.")

    finally:
        set_current_bot(orig_bot)

    print("=== [3/3] Testing Early Cancellation Skip ===")
    mock_bot.send_message.reset_mock()
    canceled_room = game_manager.create_room(
        host_tg_id=801,
        host_name="Host",
        opponent_tg_id=802,
        game_type="tictactoe"
    )
    canceled_room.status = "canceled"

    await send_game_invite_notification(
        bot=mock_bot,
        opponent_tg_id=802,
        invite_text="test",
        reply_markup=None,
        room=canceled_room
    )
    mock_bot.send_message.assert_not_called()
    print("[OK] Canceled room skips sending invite message.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
    print("\nALL INVITE CANCELLATION TESTS PASSED SUCCESSFULLY!")
