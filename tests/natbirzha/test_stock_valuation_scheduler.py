"""Listed stocks must be repriced by the live scheduler every ten minutes."""

from backend.bot.services import scheduler as scheduler_module


def run() -> None:
    scheduler = scheduler_module.scheduler
    scheduler.remove_all_jobs()
    original_start = scheduler.start
    scheduler.start = lambda: None
    try:
        scheduler_module.setup_scheduler(object())
        job = scheduler.get_job("natbirzha_stock_valuation_refresh_job")
        assert job is not None, "the scheduler must run stock valuation refreshes"
        assert "*/10" in str(job.trigger), "stock valuation refresh must run every 10 minutes"
    finally:
        scheduler.remove_all_jobs()
        scheduler.start = original_start
    print("NATBIRZHA stock valuation scheduler checks: PASS")


if __name__ == "__main__":
    run()
