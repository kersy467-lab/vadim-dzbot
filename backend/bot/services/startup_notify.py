import asyncio
from datetime import datetime
import logging
import os
import subprocess
import zoneinfo
from aiogram import Bot
from backend.config import settings, get_deploy_notify_ids

logger = logging.getLogger(__name__)


def get_latest_commit_title() -> str:
    """Retrieves the latest git commit subject / title."""
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        res = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            cwd=project_root,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    render_commit = os.environ.get("RENDER_GIT_COMMIT")
    if render_commit:
        return render_commit[:7]

    return "Обновление ветки"


def get_current_datetime_str() -> str:
    """Returns current date and time formatted as DD.MM.YYYY HH:MM:SS in configured timezone."""
    try:
        tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    return now.strftime("%d.%m.%Y %H:%M:%S")


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
        dt_str = get_current_datetime_str()
        commit_title = get_latest_commit_title()

        message_text = (
            "🚀 Деплой успешно завершен! Бот запущен.\n"
            f"📅 Дата: {dt_str}\n"
            f"📱Коммит: {commit_title}"
        )

        for chat_id in target_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                )
                logger.info(f"Deploy notification successfully sent to {chat_id}.")
            except Exception as ex:
                logger.warning(f"Could not send startup alert to {chat_id}: {ex}")
    except Exception as general_ex:
        logger.warning(f"Error in send_startup_notifications: {general_ex}")
