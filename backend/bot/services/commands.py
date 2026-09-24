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

# Команды для обычных учеников (без скрытой закрытой беты НАТБИРЖИ)
STUDENT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="now", description="⏳ Какой сейчас урок?"),
    BotCommand(command="fact", description="💡 Интересный факт"),
    BotCommand(command="stats", description="📊 Статистика ЕГЭ Арены"),
    BotCommand(command="nick", description="✏️ Сменить игровой ник"),
]

# Команды для бета-тестеров и администраторов (с /natbirzha)
TESTER_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="now", description="⏳ Какой сейчас урок?"),
    BotCommand(command="fact", description="💡 Интересный факт"),
    BotCommand(command="natbirzha", description="📈 НАТБИРЖА (Стратегия)"),
    BotCommand(command="stats", description="📊 Статистика ЕГЭ Арены"),
    BotCommand(command="nick", description="✏️ Сменить игровой ник"),
]

ADMIN_COMMANDS = [
    *TESTER_COMMANDS,
    BotCommand(command="sms", description="📣 Уведомить игроков НАТБИРЖИ"),
]

# Обратная совместимость
FULL_COMMANDS = STUDENT_COMMANDS


async def set_user_command_scope(
    bot: Bot,
    chat_id: int,
    *,
    is_tester: bool = False,
    is_admin: bool = False,
    full_access: bool = True
) -> None:
    """Give private chats commands appropriate to their Natbirzha access."""
    try:
        if not full_access:
            cmds = PUBLIC_COMMANDS
        elif is_admin:
            cmds = ADMIN_COMMANDS
        elif is_tester:
            cmds = TESTER_COMMANDS
        else:
            cmds = STUDENT_COMMANDS

        await bot.set_my_commands(
            commands=cmds,
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
    По умолчанию для всех обычных пользователей команда /natbirzha скрыта.
    Для админов и создателей сразу настраивается персональный scope с /natbirzha.
    """
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Telegram Menu Button configured for Commands menu (MenuButtonCommands).")

        # Общедоступные команды по умолчанию (без /natbirzha)
        await bot.set_my_commands(commands=STUDENT_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands=STUDENT_COMMANDS, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(commands=STUDENT_COMMANDS)

        # Персональный скоуп для главного администратора и создателей
        from backend.natbirzha.services.access_control import get_creator_tg_ids
        from backend.config import settings
        for uid in get_creator_tg_ids():
            try:
                await bot.set_my_commands(
                    commands=(
                        ADMIN_COMMANDS
                        if settings.ADMIN_ID and int(uid) == int(settings.ADMIN_ID)
                        else TESTER_COMMANDS
                    ),
                    scope=BotCommandScopeChat(chat_id=uid)
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error configuring bot commands: {e}")
