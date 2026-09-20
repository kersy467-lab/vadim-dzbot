import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.bot.handlers.settings import (
    build_settings_keyboard,
    format_settings_text,
    cb_open_settings,
    cb_toggle_currency,
    ECOSYSTEM_GUIDE_TEXT,
)
from backend.db.models import User

def test_settings_keyboard():
    kb = build_settings_keyboard(canteen_on=True, currency_on=False)
    assert len(kb.inline_keyboard) == 2
    assert "Столовая" in kb.inline_keyboard[0][0].text
    assert "✅ Вкл" in kb.inline_keyboard[0][0].text
    assert "Игровая экосистема" in kb.inline_keyboard[1][0].text
    assert "⬜ Выкл" in kb.inline_keyboard[1][0].text

def test_format_settings_text():
    text = format_settings_text(canteen_on=True, currency_on=True, coins=150)
    assert "Напоминание о столовой:" in text
    assert "150" in text
    assert "Включена" in text

async def test_cb_open_settings():
    callback = AsyncMock()
    callback.message = AsyncMock()
    user = MagicMock(spec=User)
    user.tg_id = 12345
    user.canteen_reminder_enabled = True
    user.currency_ecosystem_enabled = False
    user.coins = 200

    await cb_open_settings(callback, user)
    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert "Напоминание о столовой:" in args[0]
    kb = kwargs["reply_markup"]
    assert len(kb.inline_keyboard) == 2

async def test_cb_toggle_currency_sends_guide():
    callback = AsyncMock()
    callback.message = AsyncMock()
    user = MagicMock(spec=User)
    user.tg_id = 12345
    user.canteen_reminder_enabled = False
    user.currency_ecosystem_enabled = False
    user.coins = 100
    user.is_admin = False

    session = AsyncMock()

    # Mock toggle_user_currency_ecosystem returning True (turned ON)
    import backend.bot.handlers.settings as settings_mod
    orig_toggle = settings_mod.toggle_user_currency_ecosystem
    orig_get = settings_mod.get_user_by_tg_id
    try:
        settings_mod.toggle_user_currency_ecosystem = AsyncMock(return_value=True)
        updated_user = MagicMock(spec=User)
        updated_user.tg_id = 12345
        updated_user.currency_ecosystem_enabled = True
        updated_user.canteen_reminder_enabled = False
        updated_user.coins = 100
        updated_user.is_admin = False
        settings_mod.get_user_by_tg_id = AsyncMock(return_value=updated_user)

        await cb_toggle_currency(callback, session, user)

        # Verified guide message was sent!
        callback.message.answer.assert_called_once()
        answer_args, answer_kwargs = callback.message.answer.call_args
        assert "Игровая экосистема 11 «Б» активирована" in answer_args[0]
        assert "/cash" in answer_args[0]
        assert "/work" in answer_args[0]
        assert "Дурак" in answer_args[0]
    finally:
        settings_mod.toggle_user_currency_ecosystem = orig_toggle
        settings_mod.get_user_by_tg_id = orig_get

if __name__ == "__main__":
    test_settings_keyboard()
    test_format_settings_text()
    asyncio.run(test_cb_open_settings())
    asyncio.run(test_cb_toggle_currency_sends_guide())
    print("ALL SETTINGS UNIT TESTS PASSED!")
