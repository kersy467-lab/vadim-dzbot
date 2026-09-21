import asyncio
import os
import sys
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.abspath("."))
from backend.config import get_deploy_notify_ids, settings
from backend.bot.services.startup_notify import send_startup_notifications


async def test_startup_notify_recipients():
    old_deploy_ids = settings.DEPLOY_NOTIFY_IDS
    old_admin_id = settings.ADMIN_ID
    try:
        settings.ADMIN_ID = 999111
        settings.DEPLOY_NOTIFY_IDS = "888222, 777333"

        ids = get_deploy_notify_ids()
        assert 999111 in ids, "ADMIN_ID must be in deploy notification recipients"
        assert 888222 in ids, "ID 888222 from DEPLOY_NOTIFY_IDS must be in recipients"
        assert 777333 in ids, "ID 777333 from DEPLOY_NOTIFY_IDS must be in recipients"

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        await send_startup_notifications(mock_bot)

        sent_chat_ids = [call.kwargs.get("chat_id") for call in mock_bot.send_message.call_args_list]
        assert 999111 in sent_chat_ids
        assert 888222 in sent_chat_ids
        assert 777333 in sent_chat_ids
    finally:
        settings.DEPLOY_NOTIFY_IDS = old_deploy_ids
        settings.ADMIN_ID = old_admin_id


async def test_startup_notify_fault_tolerance():
    old_deploy_ids = settings.DEPLOY_NOTIFY_IDS
    try:
        settings.DEPLOY_NOTIFY_IDS = "111222, 333444"
        mock_bot = AsyncMock()

        # Simulate failure for one recipient
        async def mock_send(chat_id, **kwargs):
            if chat_id == 111222:
                raise RuntimeError("Telegram network glitch")
            return True

        mock_bot.send_message = AsyncMock(side_effect=mock_send)

        # Should not raise exception even if one recipient fails
        await send_startup_notifications(mock_bot)
    finally:
        settings.DEPLOY_NOTIFY_IDS = old_deploy_ids


if __name__ == "__main__":
    asyncio.run(test_startup_notify_recipients())
    asyncio.run(test_startup_notify_fault_tolerance())
    print("Startup notification tests passed successfully!")
