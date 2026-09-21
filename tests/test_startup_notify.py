import asyncio
import os
import sys
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.abspath("."))
from backend.config import get_deploy_notify_ids, settings
from backend.bot.services.startup_notify import send_startup_notifications


async def test_startup_notify_recipients():
    ids = get_deploy_notify_ids()
    assert 1053722876 in ids, "ID 1053722876 must be in deploy notification recipients"
    if settings.ADMIN_ID:
        assert settings.ADMIN_ID in ids, "ADMIN_ID must be in deploy notification recipients"

    # Mock bot
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()

    await send_startup_notifications(mock_bot)

    sent_chat_ids = [call.kwargs.get("chat_id") for call in mock_bot.send_message.call_args_list]
    assert 1053722876 in sent_chat_ids, "Deploy notification must be sent to 1053722876"
    if settings.ADMIN_ID:
        assert settings.ADMIN_ID in sent_chat_ids, "Deploy notification must be sent to ADMIN_ID"


async def test_startup_notify_fault_tolerance():
    mock_bot = AsyncMock()

    # Simulate failure for one recipient
    async def mock_send(chat_id, **kwargs):
        if chat_id == 1053722876:
            raise RuntimeError("Telegram network glitch")
        return True

    mock_bot.send_message = AsyncMock(side_effect=mock_send)

    # Should not raise exception
    await send_startup_notifications(mock_bot)


if __name__ == "__main__":
    asyncio.run(test_startup_notify_recipients())
    asyncio.run(test_startup_notify_fault_tolerance())
    print("Startup notification tests passed successfully!")
