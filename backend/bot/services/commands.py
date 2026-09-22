import logging
from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
    BotCommandScopeChat,
    MenuButtonCommands,
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
            scope=BotCommandScopeChat(chat_id=chat_id)
        )
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonCommands()
        )
    except Exception as exc:
        logger.warning("Could not set custom scope for chat %s: %s", chat_id, exc)


async def setup_bot_commands(bot: Bot):
    """
    Настраивает команды бота и кнопку открытия меню команд в интерфейсе Telegram.
    """
    try:
        await bot.set_my_commands(commands=FULL_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands=FULL_COMMANDS, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(commands=FULL_COMMANDS)

        # Синяя кнопка в строке ввода Telegram должна открывать меню команд (MenuButtonCommands)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Telegram Menu Button configured for Commands menu (MenuButtonCommands).")
    except Exception as e:
        logger.warning(f"Error configuring bot commands: {e}")
