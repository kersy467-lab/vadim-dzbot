"""Restart-safe scheduler jobs for city-order issuance and expiry."""

import logging

from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


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
