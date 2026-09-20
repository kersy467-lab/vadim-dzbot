import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.db.models import User
from backend.bot.handlers.admin.coins import (
    cb_admin_give_coins_list,
    cb_admin_give_coins_user,
    cb_admin_give_coins_fast,
    msg_admin_give_coins_custom_input,
    AdminGiveCoinsStates,
)

async def test_admin_coins_flow():
    # 1. Admin checks user list
    admin_user = MagicMock(spec=User)
    admin_user.tg_id = 999
    admin_user.role = "admin"

    callback = AsyncMock()
    callback.from_user.id = 999
    callback.message = AsyncMock()

    db_session = AsyncMock()

    student1 = MagicMock(spec=User)
    student1.tg_id = 111
    student1.full_name = "Иван Иванов"
    student1.display_name = "Иван Иванов"
    student1.coins = 150
    student1.currency_ecosystem_enabled = True

    import backend.bot.handlers.admin.coins as coins_mod
    orig_get_users = coins_mod.get_active_users
    orig_get_user = coins_mod.get_user_by_tg_id
    orig_add_coins = coins_mod.add_user_coins

    try:
        coins_mod.get_active_users = AsyncMock(return_value=[student1])
        coins_mod.get_user_by_tg_id = AsyncMock(return_value=student1)
        coins_mod.add_user_coins = AsyncMock(return_value=250)

        await cb_admin_give_coins_list(callback, db_session, admin_user)
        callback.message.edit_text.assert_called_once()
        args, kwargs = callback.message.edit_text.call_args
        assert "Выдача монет" in args[0]
        kb = kwargs["reply_markup"]
        assert any("adm_gc_u_111" in b[0].callback_data for b in kb.inline_keyboard)

        # 2. Select student 111
        callback.reset_mock()
        callback.data = "adm_gc_u_111"
        await cb_admin_give_coins_user(callback, db_session, admin_user)
        callback.message.edit_text.assert_called_once()
        args, kwargs = callback.message.edit_text.call_args
        assert "Иван Иванов" in args[0]
        assert "150" in args[0]
        kb2 = kwargs["reply_markup"]
        all_cbs = [b.callback_data for row in kb2.inline_keyboard for b in row]
        assert "adm_gc_add_111_100" in all_cbs
        assert "adm_gc_custom_111" in all_cbs

        # 3. Fast add +100 coins
        callback.reset_mock()
        callback.data = "adm_gc_add_111_100"
        bot = AsyncMock()
        await cb_admin_give_coins_fast(callback, db_session, admin_user, bot)
        coins_mod.add_user_coins.assert_called_with(db_session, 111, 100)
        bot.send_message.assert_called_once()
        bot_args, bot_kwargs = bot.send_message.call_args
        assert bot_kwargs["chat_id"] == 111
        assert "+100" in bot_kwargs["text"]

        # 4. Custom amount via FSM
        msg = AsyncMock()
        msg.from_user.id = 999
        msg.text = "350"
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={"target_tg_id": 111})

        coins_mod.add_user_coins = AsyncMock(return_value=500)
        bot.reset_mock()
        await msg_admin_give_coins_custom_input(msg, state, db_session, admin_user, bot)
        coins_mod.add_user_coins.assert_called_with(db_session, 111, 350)
        msg.answer.assert_called_once()
        assert "+350" in msg.answer.call_args[0][0]
        bot.send_message.assert_called_once()

    finally:
        coins_mod.get_active_users = orig_get_users
        coins_mod.get_user_by_tg_id = orig_get_user
        coins_mod.add_user_coins = orig_add_coins

if __name__ == "__main__":
    asyncio.run(test_admin_coins_flow())
    print("ALL ADMIN COINS TESTS PASSED!")
