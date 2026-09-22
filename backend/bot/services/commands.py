import logging
from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeChat,
    MenuButtonDefault,
)

logger = logging.getLogger(__name__)

PUBLIC_COMMANDS = [
    BotCommand(command="start", description="🎓 Открыть ЕГЭ Арену"),
    BotCommand(command="stats", description="📊 Статистика игрока по нику"),
    BotCommand(command="nick", description="✏️ Сменить игровой ник"),
]

FULL_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="now", description="⏳ Какой сейчас урок?"),
    BotCommand(command="fact", description="💡 Интересный факт"),
    BotCommand(command="natbirzha", description="📈 НАТБИРЖА (Стратегия)"),
    BotCommand(command="stats", description="📊 Статистика ЕГЭ Арены"),
    BotCommand(command="nick", description="✏️ Сменить игровой ник"),
]


async def set_user_command_scope(bot: Bot, chat_id: int, *, full_access: bool) -> None:
    """Give a private chat the right command list without exposing private features globally."""
    try:
        await bot.set_my_commands(
            commands=FULL_COMMANDS if full_access else PUBLIC_COMMANDS,
            scope=BotCommandScopeChat(chat_id=int(chat_id)),
        )
    except Exception as exc:
        logger.warning("Could not update command scope for chat %s: %s", chat_id, exc)


async def setup_bot_commands(bot: Bot):
    """Configure public defaults; full users get a per-chat override on /start."""
    try:
        await bot.set_my_commands(commands=PUBLIC_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands=PUBLIC_COMMANDS, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(commands=PUBLIC_COMMANDS)

        # A global NATBIRZHA menu button would leak a private feature to every
        # Arena player, so private apps stay in full users' personal keyboard.
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        logger.info("Public EGE Arena commands configured.")
    except Exception as e:
        logger.warning("Error configuring bot commands: %s", e)
