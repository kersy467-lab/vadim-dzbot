import asyncio
import logging
from aiogram import Bot
from backend.config import settings, get_today, get_deploy_notify_ids

logger = logging.getLogger(__name__)


async def send_startup_notifications(bot: Bot) -> None:
    """
    Sends deploy / startup completion notification to all configured admin recipients
    (ADMIN_ID and any IDs specified in DEPLOY_NOTIFY_IDS environment variable).
    """
    target_ids = get_deploy_notify_ids()
    if not target_ids:
        return

    try:
        await asyncio.sleep(1)
        today_str = get_today().strftime("%d.%m.%Y")
        is_dev_db = "sqlite" in settings.DATABASE_URL
        bot_header = (
            "🧪 **Тестовый бот (Dev) успешно запущен на localhost!**"
            if is_dev_db
            else "🚀 **Деплой успешно завершен! Бот 11 «Б» запущен.**"
        )
        db_name = "SQLite (Локальная база dev)" if is_dev_db else "Neon PostgreSQL"
        webapp_info = (
            f"📱 **Mini App для телефона:**\n{settings.WEBAPP_URL}\n"
            if settings.WEBAPP_URL.startswith("https://")
            else ""
        )
        extra_info = (
            f"🌐 Порт: `{settings.PORT}`\n🔔 Все модули и Mini App готовы к тестам!"
            if is_dev_db
            else f"🌐 Порт: `{settings.PORT}`\n🔔 Все модули, расписание, звонки и Mini App готовы к работе!"
        )
        message_text = (
            f"{bot_header}\n\n"
            f"📅 **Дата:** `{today_str}`\n"
            f"⚡ База данных: `{db_name}`\n"
            f"{extra_info}\n"
            f"{webapp_info}"
        )

        for chat_id in target_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    parse_mode="Markdown"
                )
                logger.info(f"Deploy notification successfully sent to {chat_id}.")
            except Exception as ex:
                logger.warning(f"Could not send startup alert to {chat_id}: {ex}")
    except Exception as general_ex:
        logger.warning(f"Error in send_startup_notifications: {general_ex}")
