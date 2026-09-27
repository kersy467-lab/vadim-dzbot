"""Best-effort private Telegram notifications for company actions."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.models.company import NatCompany


logger = logging.getLogger(__name__)


def _current_bot():
    try:
        from backend.bot.bot import get_current_bot

        return get_current_bot()
    except Exception:
        logger.exception("Could not resolve the Telegram bot for a player DM")
        return None


async def send_company_dm(session: AsyncSession, company_id: int, message: str) -> bool:
    """Send one private message to a company's owner after its action committed.

    The helper intentionally treats delivery as best effort: a user who has
    never opened the bot, blocked it, or has a transient Telegram failure must
    not cause an already-committed game action to fail in the API.
    """
    try:
        telegram_id = await session.scalar(
            select(User.tg_id)
            .join(NatCompany, NatCompany.user_id == User.id)
            .where(NatCompany.id == int(company_id))
        )
    except Exception:
        logger.warning("Could not resolve owner of company %s for a private notification", company_id, exc_info=True)
        return False
    if telegram_id is None or int(telegram_id) <= 0:
        return False

    bot = _current_bot()
    if bot is None:
        logger.info("Skipped company DM because the Telegram bot is unavailable (company=%s)", company_id)
        return False

    try:
        await bot.send_message(chat_id=int(telegram_id), text=message, parse_mode=None)
        return True
    except Exception:
        logger.warning(
            "Could not send a company notification to Telegram user %s",
            telegram_id,
            exc_info=True,
        )
        return False


__all__ = ["send_company_dm"]
