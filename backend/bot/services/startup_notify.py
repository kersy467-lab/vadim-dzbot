import asyncio
import hashlib
from datetime import datetime
import logging
import os
import subprocess
import zoneinfo
from aiogram import Bot
from backend.config import settings, get_deploy_notify_ids

logger = logging.getLogger(__name__)


def get_deploy_identity() -> str | None:
    """Return a stable deployment ID shared by every process started for one commit."""
    render_commit = str(os.environ.get("RENDER_GIT_COMMIT", "")).strip()
    if render_commit:
        return render_commit
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3, cwd=project_root,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None


async def _send_notification_once(bot: Bot, deployment_id: str, chat_id: int, text: str) -> bool:
    """Atomically claim a per-deployment/per-recipient alert before sending it."""
    from sqlalchemy.dialects.postgresql import insert as postgres_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from backend.db.models import ClassSetting
    from backend.db.session import async_session_factory

    digest = hashlib.sha256(f"{deployment_id}:{int(chat_id)}".encode()).hexdigest()[:24]
    marker_key = f"deploy_notification_{digest}"
    async with async_session_factory() as session:
        async with session.begin():
            dialect = session.get_bind().dialect.name
            if dialect == "postgresql":
                statement = postgres_insert(ClassSetting).values(
                    key=marker_key, value=deployment_id,
                ).on_conflict_do_nothing(index_elements=[ClassSetting.key])
            elif dialect == "sqlite":
                statement = sqlite_insert(ClassSetting).values(
                    key=marker_key, value=deployment_id,
                ).on_conflict_do_nothing(index_elements=[ClassSetting.key])
            else:
                if await session.get(ClassSetting, marker_key):
                    return False
                session.add(ClassSetting(key=marker_key, value=deployment_id))
                await session.flush()
                statement = None

            if statement is not None:
                result = await session.execute(statement)
                if not result.rowcount:
                    return False
            # Keep the unique-key claim uncommitted during the Telegram request.
            # A second process waits on the same key and skips after this commit.
            await bot.send_message(chat_id=chat_id, text=text)
    return True


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
        deployment_id = get_deploy_identity()

        message_text = (
            "🚀 Деплой успешно завершен! Бот запущен.\n"
            f"📅 Дата: {dt_str}\n"
            f"📱Коммит: {commit_title}"
        )

        for chat_id in target_ids:
            try:
                if deployment_id:
                    sent = await _send_notification_once(bot, deployment_id, chat_id, message_text)
                    if not sent:
                        logger.info("Duplicate deploy notification skipped for %s (%s).", chat_id, deployment_id[:12])
                        continue
                else:
                    await bot.send_message(chat_id=chat_id, text=message_text)
                logger.info("Deploy notification successfully sent to %s.", chat_id)
            except Exception as ex:
                logger.warning(f"Could not send startup alert to {chat_id}: {ex}")
    except Exception as general_ex:
        logger.warning(f"Error in send_startup_notifications: {general_ex}")
