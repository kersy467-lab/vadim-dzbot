import asyncio
import os
import sys
from unittest.mock import AsyncMock


sys.path.insert(0, os.path.abspath("."))
from backend.config import get_deploy_notify_ids, settings
import backend.bot.services.startup_notify as startup_notify
from backend.bot.services.startup_notify import send_startup_notifications


async def test_startup_notify_recipients():
    old_deploy_ids = settings.DEPLOY_NOTIFY_IDS
    old_admin_id = settings.ADMIN_ID
    old_deploy_identity = startup_notify.get_deploy_identity
    try:
        startup_notify.get_deploy_identity = lambda: None
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

        sent_texts = [call.kwargs.get("text") for call in mock_bot.send_message.call_args_list]
        for text in sent_texts:
            assert "🚀 Деплой успешно завершен! Бот запущен." in text
            assert "📅 Дата: " in text
            assert "📱Коммит: " in text
    finally:
        settings.DEPLOY_NOTIFY_IDS = old_deploy_ids
        settings.ADMIN_ID = old_admin_id
        startup_notify.get_deploy_identity = old_deploy_identity


async def test_startup_notify_fault_tolerance():
    old_deploy_ids = settings.DEPLOY_NOTIFY_IDS
    old_deploy_identity = startup_notify.get_deploy_identity
    try:
        startup_notify.get_deploy_identity = lambda: None
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
        startup_notify.get_deploy_identity = old_deploy_identity


def test_startup_notification_is_sent_once_for_same_deployment():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    import backend.db.session as db_session
    from backend.db.models import ClassSetting

    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        old_factory = db_session.async_session_factory
        old_recipients = startup_notify.get_deploy_notify_ids
        old_identity = startup_notify.get_deploy_identity
        old_sleep = startup_notify.asyncio.sleep
        try:
            async with engine.begin() as connection:
                await connection.run_sync(ClassSetting.__table__.create)
            db_session.async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
            startup_notify.get_deploy_notify_ids = lambda: {101, 202}
            startup_notify.get_deploy_identity = lambda: "commit-sha-123"
            startup_notify.asyncio.sleep = AsyncMock()

            mock_bot = AsyncMock()
            mock_bot.send_message = AsyncMock()
            await startup_notify.send_startup_notifications(mock_bot)
            await startup_notify.send_startup_notifications(mock_bot)

            delivered_ids = [call.kwargs["chat_id"] for call in mock_bot.send_message.call_args_list]
            assert sorted(delivered_ids) == [101, 202], delivered_ids
            async with db_session.async_session_factory() as session:
                markers = list((await session.scalars(select(ClassSetting.key).where(
                    ClassSetting.key.like("deploy_notification_%"),
                ))).all())
            assert len(markers) == 2
        finally:
            db_session.async_session_factory = old_factory
            startup_notify.get_deploy_notify_ids = old_recipients
            startup_notify.get_deploy_identity = old_identity
            startup_notify.asyncio.sleep = old_sleep
            await engine.dispose()

    asyncio.run(check())


if __name__ == "__main__":
    asyncio.run(test_startup_notify_recipients())
    asyncio.run(test_startup_notify_fault_tolerance())
    test_startup_notification_is_sent_once_for_same_deployment()
    print("Startup notification tests passed successfully!")
