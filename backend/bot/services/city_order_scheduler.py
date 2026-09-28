"""Restart-safe scheduler jobs for city-order issuance and expiry."""

from datetime import datetime
from html import escape
import logging

from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def _format_amount(value: float) -> str:
    formatted = f"{float(value):,.6f}".rstrip("0").rstrip(".")
    return formatted.replace(",", " ").replace(".", ",")


def format_city_order_announcement(order: dict) -> str:
    """Render an issued order with its actual reserved payout for Telegram."""
    quantity = _format_amount(order.get("quantity", 0))
    unit_price = _format_amount(order.get("unit_price", 0))
    total = _format_amount(order.get("reserved_cash", 0))
    unit = escape(str(order.get("unit") or "ед."))
    expires_at = str(order.get("expires_at") or "")
    try:
        deadline = datetime.fromisoformat(expires_at).strftime("%d.%m в %H:%M")
    except ValueError:
        deadline = expires_at
    return (
        "🏙 <b>Новый заказ города</b>\n"
        f"🏭 Отрасль: <b>{escape(str(order.get('industry_name') or order.get('industry') or ''))}</b>\n"
        f"📦 Товар: <b>{escape(str(order.get('item_name') or order.get('item_id') or ''))}</b>\n"
        f"Объём: <b>{quantity} {unit}</b>\n"
        f"Цена: <b>{unit_price} cash/{unit}</b> (городская премия +20% к базовой цене)\n"
        f"Выплата за весь объём: <b>{total} cash</b>\n"
        f"⏳ Действует до: <b>{escape(deadline)}</b>\n"
        "Сдать товар можно в Биржа → Городские заказы."
    )


async def issue_city_order_slot() -> None:
    try:
        from backend.db.session import async_session_factory
        from backend.natbirzha.config import get_game_now
        from backend.natbirzha.services.city_order_service import CityOrderService

        async with async_session_factory() as session:
            result = await CityOrderService.issue_due(session, now=get_game_now())
            if result.get("created") or result.get("expired_count"):
                await session.commit()
                if result.get("created"):
                    logger.info("City order issued: %s", result["order"])
                    from backend.natbirzha.services.event_broadcaster import EventBroadcaster

                    delivered = await EventBroadcaster.send_message(
                        format_city_order_announcement(result["order"])
                    )
                    if not delivered:
                        logger.error(
                            "City order %s was issued but its group notification could not be delivered",
                            result["order"].get("id"),
                        )
    except Exception:
        logger.exception("Error issuing scheduled city order")


async def expire_city_orders() -> None:
    try:
        from backend.db.session import async_session_factory
        from backend.natbirzha.config import get_game_now
        from backend.natbirzha.services.city_order_service import CityOrderService

        async with async_session_factory() as session:
            expired = await CityOrderService.expire_due(session, now=get_game_now())
            if expired:
                await session.commit()
                logger.info("Expired %s city orders", expired)
    except Exception:
        logger.exception("Error expiring city orders")


def register_city_order_jobs(scheduler) -> None:
    from backend.natbirzha.config import get_game_tz

    timezone = get_game_tz()
    scheduler.add_job(
        issue_city_order_slot,
        trigger=CronTrigger(minute="0,30", timezone=timezone),
        id="natbirzha_city_order_issue_job",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        expire_city_orders,
        trigger=CronTrigger(minute="*", timezone=timezone),
        id="natbirzha_city_order_expiry_job",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


__all__ = ["expire_city_orders", "issue_city_order_slot", "register_city_order_jobs"]
