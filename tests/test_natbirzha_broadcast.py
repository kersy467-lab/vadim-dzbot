import os
import sys
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.bot.handlers.admin.natbirzha_notice import cmd_natbirzha_notice
from backend.bot.services.commands import set_user_command_scope


def _message(text):
    message = MagicMock()
    message.text = text
    message.from_user.id = 900
    message.chat.type = "private"
    message.answer = AsyncMock()
    return message


def _database_with_recipients(ids):
    result = MagicMock()
    result.scalars.return_value.all.return_value = ids
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def test_natbirzha_notice_sends_once_per_registered_player_and_reports_counts():
    async def run():
        message = _message("/sms Продайте уголь по 30")
        session = _database_with_recipients([101, 202, 101])
        bot = MagicMock()
        bot.send_message = AsyncMock()

        await cmd_natbirzha_notice(
            message,
            bot,
            SimpleNamespace(role="admin"),
            session,
        )

        assert [call.kwargs["chat_id"] for call in bot.send_message.await_args_list] == [101, 202]
        query_sql = str(session.execute.await_args.args[0])
        assert "JOIN nat_companies" in query_sql
        assert "users.tg_id" in query_sql
        assert all(call.kwargs["text"] == "Продайте уголь по 30" for call in bot.send_message.await_args_list)
        assert all(call.kwargs["parse_mode"] is None for call in bot.send_message.await_args_list)
        response = message.answer.await_args.args[0]
        assert "Адресатов: 2" in response
        assert "Доставлено: 2" in response
        assert "Ошибки отправки: 0" in response

    asyncio.run(run())


def test_natbirzha_notice_counts_failed_delivery_and_continues():
    async def run():
        message = _message("/natnotice Проверка")
        session = _database_with_recipients([101, 202, 303])
        bot = MagicMock()

        async def send_message(*, chat_id, **kwargs):
            if chat_id == 202:
                raise RuntimeError("blocked")

        bot.send_message = AsyncMock(side_effect=send_message)

        await cmd_natbirzha_notice(
            message,
            bot,
            SimpleNamespace(role="admin"),
            session,
        )

        assert bot.send_message.await_count == 3
        response = message.answer.await_args.args[0]
        assert "Адресатов: 3" in response
        assert "Доставлено: 2" in response
        assert "Ошибки отправки: 1" in response
        assert "TG ID недоставленных: 202" in response

    asyncio.run(run())


def test_natbirzha_notice_rejects_empty_message_without_querying_or_sending():
    async def run():
        message = _message("/natnotice   ")
        session = _database_with_recipients([])
        bot = MagicMock()
        bot.send_message = AsyncMock()

        await cmd_natbirzha_notice(
            message,
            bot,
            SimpleNamespace(role="admin"),
            session,
        )

        session.execute.assert_not_awaited()
        bot.send_message.assert_not_awaited()
        assert "текст" in message.answer.await_args.args[0].lower()

    asyncio.run(run())


def test_natbirzha_notice_ignores_non_admins():
    async def run():
        message = _message("/natnotice Не слать")
        session = _database_with_recipients([101])
        bot = MagicMock()
        bot.send_message = AsyncMock()

        await cmd_natbirzha_notice(
            message,
            bot,
            SimpleNamespace(role="student"),
            session,
        )

        session.execute.assert_not_awaited()
        bot.send_message.assert_not_awaited()
        message.answer.assert_not_awaited()

    asyncio.run(run())


def test_sms_command_is_visible_only_in_admin_command_menu():
    async def run():
        admin_bot = SimpleNamespace(
            set_my_commands=AsyncMock(),
            set_chat_menu_button=AsyncMock(),
        )
        tester_bot = SimpleNamespace(
            set_my_commands=AsyncMock(),
            set_chat_menu_button=AsyncMock(),
        )

        await set_user_command_scope(
            admin_bot,
            chat_id=900,
            is_admin=True,
            is_tester=True,
            full_access=True,
        )
        await set_user_command_scope(
            tester_bot,
            chat_id=901,
            is_admin=False,
            is_tester=True,
            full_access=True,
        )

        admin_names = [
            command.command
            for command in admin_bot.set_my_commands.await_args.kwargs["commands"]
        ]
        tester_names = [
            command.command
            for command in tester_bot.set_my_commands.await_args.kwargs["commands"]
        ]
        assert "sms" in admin_names
        assert "sms" not in tester_names

    asyncio.run(run())


if __name__ == "__main__":
    test_natbirzha_notice_sends_once_per_registered_player_and_reports_counts()
    test_natbirzha_notice_counts_failed_delivery_and_continues()
    test_natbirzha_notice_rejects_empty_message_without_querying_or_sending()
    test_natbirzha_notice_ignores_non_admins()
    test_sms_command_is_visible_only_in_admin_command_menu()
    print("NATBIRZHA admin notice tests: PASS")
