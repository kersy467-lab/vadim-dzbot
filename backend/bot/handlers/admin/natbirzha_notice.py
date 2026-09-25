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


# Keep the old names as aliases while exposing /sms as the official command.
@router.message(Command("sms", "natnotice", "natnoice"))
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
            "⚠️ Укажите текст сообщения.\nПример: /sms Продайте уголь по 30",
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
    failed_recipient_ids: list[int] = []
    for recipient_id in recipient_ids:
        try:
            await bot.send_message(
                chat_id=recipient_id,
                text=body,
                parse_mode=None,
            )
            delivered += 1
        except Exception as exc:
            failed_recipient_ids.append(recipient_id)
            logger.warning(
                "Natbirzha notice delivery failed for Telegram user %s: %s",
                recipient_id,
                exc,
            )

    failed = len(failed_recipient_ids)
    report = (
        "📢 Рассылка игрокам НАТБИРЖИ завершена.\n"
        f"👥 Адресатов: {len(recipient_ids)}\n"
        f"✅ Доставлено: {delivered}\n"
        f"❌ Ошибки отправки: {failed}"
    )
    if failed_recipient_ids:
        report += (
            "\n\nTelegram не смог написать этим игрокам. Частая причина — игрок не нажимал /start "
            "в личном чате с ботом или заблокировал его.\n"
            "TG ID недоставленных: "
            + ", ".join(str(tg_id) for tg_id in failed_recipient_ids[:20])
        )
        if failed > 20:
            report += f" и ещё {failed - 20}"
    await message.answer(report, parse_mode=None)


@router.message(Command("obv", "gosobv", "gos_announcement"))
async def cmd_state_announcement(
    message: Message,
    bot: Bot,
    current_user: User,
    db_session: AsyncSession,
) -> None:
    """Send an official state announcement into the group chat with optional owner tag."""
    if not is_admin(current_user, message.from_user.id):
        return

    import html
    from sqlalchemy import func, or_
    from backend.natbirzha.services.event_broadcaster import EventBroadcaster

    parts = (message.text or "").split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""

    target_user = None
    if message.reply_to_message and message.reply_to_message.from_user:
        if not message.reply_to_message.from_user.is_bot:
            target_user = message.reply_to_message.from_user

    if not args and not target_user:
        help_text = (
            "🏛 <b>Команда /obv (Государственное объявление)</b>\n\n"
            "Публикует официальное сообщение от лица государства в игровую группу.\n\n"
            "<b>Форматы использования:</b>\n"
            "• <code>/obv [текст]</code> — обычное государственное объявление\n"
            "• <code>/obv @username [текст]</code> — объявление с тегом гражданина\n"
            "• <code>/obv [ТИКЕР] [текст]</code> — объявление компании с тегом владельца\n"
            "• <i>Или ответьте (reply) <code>/obv [текст]</code> на любое сообщение игрока</i>"
        )
        await message.answer(help_text, parse_mode="HTML")
        return

    owner_tag = None
    company_name = None
    company_ticker = None
    announcement_body = args

    if target_user:
        if target_user.username:
            owner_tag = f"@{target_user.username}"
        else:
            r_name = html.escape(target_user.full_name or "Гражданин")
            owner_tag = f'<a href="tg://user?id={target_user.id}">{r_name}</a>'

        u_stmt = select(User).where(User.tg_id == target_user.id)
        u_row = (await db_session.execute(u_stmt)).scalars().first()
        if u_row:
            c_stmt = select(NatCompany).where(NatCompany.user_id == u_row.id)
            c_row = (await db_session.execute(c_stmt)).scalars().first()
            if c_row:
                company_name = c_row.name
                company_ticker = c_row.ticker
    elif args:
        tokens = args.split(maxsplit=1)
        cand = tokens[0].strip()
        rest = tokens[1].strip() if len(tokens) > 1 else ""

        if cand.startswith("@") and len(cand) > 1:
            uname = cand.lstrip("@").strip()
            owner_tag = f"@{uname}"
            announcement_body = rest

            u_stmt = select(User).where(func.lower(User.username) == uname.lower())
            u_row = (await db_session.execute(u_stmt)).scalars().first()
            if u_row:
                c_stmt = select(NatCompany).where(NatCompany.user_id == u_row.id)
                c_row = (await db_session.execute(c_stmt)).scalars().first()
                if c_row:
                    company_name = c_row.name
                    company_ticker = c_row.ticker
        elif rest:
            # Check if cand is a company ticker or name
            c_stmt = select(NatCompany).where(
                or_(
                    func.upper(NatCompany.custom_ticker) == cand.upper(),
                    func.upper(NatCompany.name) == cand.upper(),
                )
            )
            c_row = (await db_session.execute(c_stmt)).scalars().first()
            if not c_row:
                all_comps = (await db_session.execute(select(NatCompany))).scalars().all()
                for comp in all_comps:
                    if comp.ticker.upper() == cand.upper():
                        c_row = comp
                        break

            if c_row:
                company_name = c_row.name
                company_ticker = c_row.ticker
                announcement_body = rest

                u_stmt = select(User).where(User.id == c_row.user_id)
                u_row = (await db_session.execute(u_stmt)).scalars().first()
                if u_row:
                    if u_row.username:
                        owner_tag = f"@{u_row.username}"
                    elif u_row.tg_id:
                        u_name = html.escape(u_row.display_name or "Владелец")
                        owner_tag = f'<a href="tg://user?id={u_row.tg_id}">{u_name}</a>'

    if not announcement_body.strip():
        await message.answer("⚠️ Текст объявления не может быть пустым.", parse_mode="HTML")
        return

    sent = await EventBroadcaster.broadcast_state_announcement(
        message=announcement_body,
        owner_tag=owner_tag,
        company_name=company_name,
        ticker=company_ticker,
    )

    if sent:
        await message.answer("✅ Государственное объявление успешно опубликовано в группе!", parse_mode="HTML")
    else:
        await message.answer(
            "⚠️ Не удалось опубликовать объявление в группе.\n"
            "Убедитесь, что бот добавлен в группу и у него есть права отправки сообщений.",
            parse_mode="HTML",
        )
