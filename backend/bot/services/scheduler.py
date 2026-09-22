import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from backend.config import settings
from backend.bot.services.notifier import (
    send_evening_digest, check_and_send_duty_reminder, send_monday_duty_personal_reminder
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

def setup_scheduler(bot: Bot):
    try:
        hour, minute = settings.NOTIFICATION_TIME_EVENING.split(":")
        trigger = CronTrigger(
            day_of_week="mon-fri,sun",
            hour=int(hour),
            minute=int(minute),
            timezone=settings.TIMEZONE
        )

        scheduler.add_job(
            send_evening_digest,
            trigger=trigger,
            args=[bot],
            id="evening_digest_job",
            replace_existing=True
        )

        # Проверка смены дежурных каждое утро в 07:30
        scheduler.add_job(
            check_and_send_duty_reminder,
            trigger=CronTrigger(hour=7, minute=30, timezone=settings.TIMEZONE),
            args=[bot],
            id="duty_rotation_check_job",
            replace_existing=True
        )

        # Персональное напоминание дежурным в понедельник в 06:00 утра
        scheduler.add_job(
            send_monday_duty_personal_reminder,
            trigger=CronTrigger(day_of_week="mon", hour=6, minute=0, timezone=settings.TIMEZONE),
            args=[bot],
            id="monday_duty_personal_reminder_job",
            replace_existing=True
        )

        # Автоматическая очистка устаревших отметок чеклиста и прошлых фактов в 00:05
        async def run_daily_cleanup():
            try:
                from backend.db.session import async_session_factory
                from backend.db.crud.homework import cleanup_past_homework_statuses
                from backend.bot.services.facts import cleanup_past_facts
                async with async_session_factory() as session:
                    cleaned = await cleanup_past_homework_statuses(session)
                    if cleaned > 0:
                        logger.info(f"Daily checklist cleanup: deleted {cleaned} obsolete records from past homework.")
                    cleaned_facts = await cleanup_past_facts(session)
                    if cleaned_facts > 0:
                        logger.info(f"Daily facts cleanup: deleted {cleaned_facts} obsolete past facts.")
            except Exception as ex:
                logger.error(f"Error in daily cleanup: {ex}")

        # Автоматические поздравления с Днём Рождения в 00:00 (Екатеринбург) в важные объявления
        from backend.bot.services.birthdays import check_and_send_birthday_greetings
        scheduler.add_job(
            check_and_send_birthday_greetings,
            trigger=CronTrigger(hour=0, minute=0, timezone=settings.TIMEZONE),
            args=[bot],
            id="daily_birthday_greetings_job",
            replace_existing=True
        )

        scheduler.add_job(
            run_daily_cleanup,
            trigger=CronTrigger(hour=0, minute=5, timezone=settings.TIMEZONE),
            id="daily_cleanup_job",
            replace_existing=True
        )

        # Автоматическая генерация интересного факта каждые полчаса (:00 и :30)
        async def run_half_hour_fact_generation():
            try:
                from backend.db.session import async_session_factory
                from backend.bot.services.facts import get_or_generate_slot_fact
                async with async_session_factory() as session:
                    fact = await get_or_generate_slot_fact(session)
                    logger.info(f"Interesting fact ready for {fact.date} {fact.hour:02d}:{fact.minute:02d}: '{fact.title}' ({fact.category})")
            except Exception as ex:
                logger.error(f"Error pre-generating fact: {ex}")

        scheduler.add_job(
            run_half_hour_fact_generation,
            trigger=CronTrigger(minute="0,30", timezone=settings.TIMEZONE),
            id="half_hour_fact_generation_job",
            replace_existing=True
        )

        # Напоминание о столовой после 5 урока (проверка каждую минуту в учебные дни)
        from backend.bot.services.canteen import check_canteen_time_job
        scheduler.add_job(
            check_canteen_time_job,
            trigger=CronTrigger(day_of_week="mon-fri", minute="*", timezone=settings.TIMEZONE),
            args=[bot],
            id="canteen_reminder_check_job",
            replace_existing=True
        )

        # Автоматическая отправка персональных расписаний (проверка каждую минуту)
        from backend.bot.services.custom_schedule import send_due_custom_schedules
        scheduler.add_job(
            send_due_custom_schedules,
            trigger=CronTrigger(minute="*", timezone=settings.TIMEZONE),
            args=[bot],
            id="custom_schedule_dispatch_job",
            replace_existing=True
        )


        # Natbirzha: глобальный почасовой тик производства в :00
        async def run_natbirzha_hourly_tick():
            try:
                from backend.db.session import async_session_factory
                from backend.natbirzha.services.production_service import ProductionTickEngine
                async with async_session_factory() as session:
                    res = await ProductionTickEngine.process_global_scheduled_tick(session)
                    ticks = res.get("ticks_processed", 0) if isinstance(res, dict) else int(res or 0)
                    if ticks > 0:
                        logger.info(f"Natbirzha tick processed {ticks} factories.")
            except Exception as ex:
                logger.error(f"Error in natbirzha hourly tick: {ex}")

        scheduler.add_job(
            run_natbirzha_hourly_tick,
            trigger=CronTrigger(minute=0, timezone=settings.TIMEZONE),
            id="natbirzha_hourly_tick_job",
            replace_existing=True
        )

        # Natbirzha: restart-safe tournament lifecycle. The DB state, not the
        # scheduler process, is the source of truth, so restarts cannot skip an
        # activation or pay rewards twice.
        async def run_natbirzha_tournament_tick():
            try:
                from backend.db.session import async_session_factory
                from backend.natbirzha.config import get_game_now
                from backend.natbirzha.services.tournament_service import TournamentService
                async with async_session_factory() as session:
                    result = await TournamentService.tick(session, get_game_now())
                    await session.commit()
                    if result["activated"] or result["resolved"]:
                        logger.info("Natbirzha tournament tick: %s", result)
            except Exception as ex:
                logger.error(f"Error in natbirzha tournament tick: {ex}")

        scheduler.add_job(
            run_natbirzha_tournament_tick,
            trigger=CronTrigger(minute="*", timezone=settings.TIMEZONE),
            id="natbirzha_tournament_tick_job",
            replace_existing=True
        )

        # Natbirzha: cache official CBR reference prices. A failed refresh does
        # not overwrite the last known good snapshots; the trade service applies
        # its own 72-hour staleness circuit breaker.
        async def run_natbirzha_reference_rate_refresh():
            try:
                from backend.db.session import async_session_factory
                from backend.natbirzha.services.reference_instrument_service import ReferenceInstrumentService
                async with async_session_factory() as session:
                    rows = await ReferenceInstrumentService.refresh(session)
                    await session.commit()
                    logger.info("Natbirzha reference rates refreshed: %s", [row.instrument_code for row in rows])
            except Exception as ex:
                logger.error(f"Error refreshing Natbirzha reference rates: {ex}")

        scheduler.add_job(
            run_natbirzha_reference_rate_refresh,
            trigger=CronTrigger(minute="*/30", timezone=settings.TIMEZONE),
            id="natbirzha_reference_rate_refresh_job",
            replace_existing=True,
        )

        # Natbirzha: a listed company changes its audited valuation as cash,
        # assets and closed profit change. Reprice all due stocks independently
        # of a player opening the market, so every holder sees the same price.
        async def run_natbirzha_stock_valuation_refresh():
            try:
                from backend.db.session import async_session_factory
                from backend.natbirzha.services.stock_service import StockService
                async with async_session_factory() as session:
                    refreshed = await StockService.refresh_due_valuations(session, commit=True)
                    if refreshed:
                        logger.info("Natbirzha stock valuations refreshed: %s", refreshed)
            except Exception as ex:
                logger.error(f"Error refreshing Natbirzha stock valuations: {ex}")

        scheduler.add_job(
            run_natbirzha_stock_valuation_refresh,
            trigger=CronTrigger(minute="*/10", timezone=settings.TIMEZONE),
            id="natbirzha_stock_valuation_refresh_job",
            replace_existing=True,
        )

        # Natbirzha: retries pending coupons and maturities without duplicate
        # payment after restarts. Settlement rows are the durable source of truth.
        async def run_natbirzha_bond_settlement():
            try:
                from backend.db.session import async_session_factory
                from backend.natbirzha.services.state_bond_service import StateBondService
                async with async_session_factory() as session:
                    result = await StateBondService.settle_due(session, commit=True)
                    if result["coupon_payments"] or result["maturity_payments"]:
                        logger.info("Natbirzha bond settlement: %s", result)
            except Exception as ex:
                logger.error(f"Error settling Natbirzha bonds: {ex}")

        scheduler.add_job(
            run_natbirzha_bond_settlement,
            trigger=CronTrigger(minute="*/5", timezone=settings.TIMEZONE),
            id="natbirzha_bond_settlement_job",
            replace_existing=True,
        )

        # Natbirzha: ежедневная выплата дивидендов и ликвидации в 00:01
        async def run_natbirzha_daily_settlement():
            try:
                from backend.db.session import async_session_factory
                from backend.natbirzha.services.dividend_service import DividendService
                from backend.natbirzha.services.bankruptcy_service import BankruptcyService
                async with async_session_factory() as session:
                    await DividendService.settle_all_public_dividends(session)
                    await BankruptcyService.process_daily_liquidations(session)
                    logger.info("Natbirzha daily settlement completed.")
            except Exception as ex:
                logger.error(f"Error in natbirzha daily settlement: {ex}")

        scheduler.add_job(
            run_natbirzha_daily_settlement,
            trigger=CronTrigger(hour=0, minute=1, timezone=settings.TIMEZONE),
            id="natbirzha_daily_settlement_job",
            replace_existing=True
        )

        scheduler.start()
        logger.info(f"Scheduler started with evening digest ({settings.NOTIFICATION_TIME_EVENING}), canteen reminder, duty check (07:30), Monday duty reminder (06:00), fact rotation (every 30m), daily cleanup (00:05), and Natbirzha tick/settlement ({settings.TIMEZONE})")


    except Exception as e:
        logger.error(f"Error setting up scheduler: {e}")
