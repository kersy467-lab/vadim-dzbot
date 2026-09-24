import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.bot.handlers.admin.helpers import is_admin
from backend.db.models import User
from backend.natbirzha.models.company import NatCompany

logger = logging.getLogger(__name__)
router = Router(name="admin_natbirzha_notice_router")


async def _get_natbirzha_recipient_ids(db_session: AsyncSession) -> list[int]:
    result = await db_session.execute(
        select(User.tg_id)
        .join(NatCompany, NatCompany.user_id == User.id)
        .distinct()
        .order_by(User.tg_id)
    )
    return list(dict.fromkeys(int(tg_id) for tg_id in result.scalars().all() if tg_id is not None))


# Accept the typo used by the admin as a backwards-compatible alias.
@router.message(Command("natnotice", "natnoice"))
async def cmd_natbirzha_notice(
    message: Message,
    bot: Bot,
    current_user: User,
    db_session: AsyncSession,
) -> None:
    if message.chat.type != "private" or not is_admin(current_user, message.from_user.id):
        return

    parts = (message.text or "").split(maxsplit=1)
    body = parts[1].strip() if len(parts) > 1 else ""
    if not body:
        await message.answer(
            "⚠️ Укажите текст сообщения.\nПример: /natnotice Продайте уголь по 30",
            parse_mode=None,
        )
        return

    try:
        recipient_ids = await _get_natbirzha_recipient_ids(db_session)
    except Exception:
        logger.exception("Could not load Natbirzha broadcast recipients")
        await message.answer(
            "❌ Не удалось получить список игроков НАТБИРЖИ.",
            parse_mode=None,
        )
        return

    delivered = 0
    failed = 0
    for recipient_id in recipient_ids:
        try:
            await bot.send_message(
                chat_id=recipient_id,
                text=body,
                parse_mode=None,
            )
            delivered += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "Natbirzha notice delivery failed for Telegram user %s: %s",
                recipient_id,
                exc,
            )

    await message.answer(
        "📢 Рассылка игрокам НАТБИРЖИ завершена.\n"
        f"✅ Доставлено: {delivered}\n"
        f"❌ Ошибки отправки: {failed}",
        parse_mode=None,
    )
