import logging
from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    MenuButtonDefault,
    MenuButtonWebApp,
    WebAppInfo
)
from backend.config import get_natbirzha_webapp_url, settings

logger = logging.getLogger(__name__)

async def setup_bot_commands(bot: Bot):
    """
    Настраивает команды бота и кнопку открытия Mini App в интерфейсе Telegram.
    """
    try:
        commands = [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="now", description="⏳ Какой сейчас урок?"),
            BotCommand(command="fact", description="💡 Интересный факт"),
            BotCommand(command="natbirzha", description="📈 НАТБИРЖА (Стратегия)"),
        ]
        await bot.set_my_commands(commands=commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands=commands, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(commands=commands)

        natbirzha_url = get_natbirzha_webapp_url(settings.WEBAPP_URL)
        if natbirzha_url.startswith("https://"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📈 НАТБИРЖА",
                    web_app=WebAppInfo(url=natbirzha_url)
                )
            )
            logger.info("Telegram Menu Button configured for NATBIRZHA: %s", natbirzha_url)
        else:
            await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
            logger.info("Bot commands updated: /start and /fact (💡 Интересный факт) registered.")
    except Exception as e:
        logger.warning(f"Error configuring bot commands: {e}")

