"""Persist exact rolling market-liquidity totals on each half-hour boundary."""

import logging

from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


async def refresh_liquidity_snapshot() -> None:
    try:
        from backend.db.session import async_session_factory
        from backend.natbirzha.config import get_game_now, get_game_tz, normalize_dt
        from backend.natbirzha.services.liquidity_service import LiquidityService

        now = normalize_dt(get_game_now())
        if now is None:
            return
        window_end = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
        async with async_session_factory() as session:
            snapshot = await LiquidityService.record_snapshot(session, now=window_end)
            await session.commit()
            logger.info(
                "Recorded market liquidity for %s (%s sales)",
                snapshot.window_end.replace(tzinfo=get_game_tz()).isoformat(),
                snapshot.sale_count,
            )
    except Exception:
        logger.exception("Error recording market-liquidity snapshot")


def register_liquidity_jobs(scheduler) -> None:
    from backend.natbirzha.config import get_game_tz

    scheduler.add_job(
        refresh_liquidity_snapshot,
        trigger=CronTrigger(minute="0,30", timezone=get_game_tz()),
        id="natbirzha_liquidity_snapshot_job",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


__all__ = ["refresh_liquidity_snapshot", "register_liquidity_jobs"]
