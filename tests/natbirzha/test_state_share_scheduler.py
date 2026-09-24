"""Daily state-share settlement is separate from hourly public-stock dividends."""

import asyncio
from importlib.util import find_spec

from backend.bot.services import scheduler as scheduler_module


def test_daily_financial_job_calls_state_share_settlement(monkeypatch) -> None:
    assert find_spec("backend.natbirzha.services.state_share_service") is not None
    from backend.db import session as db_session
    from backend.natbirzha.services.bankruptcy_service import BankruptcyService
    from backend.natbirzha.services.state_share_service import StateShareService

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    calls: list[str] = []

    async def record_share_settlement(_session):
        calls.append("shares")
        return {"status": "settled", "total_paid": 0}

    async def record_liquidations(_session):
        calls.append("liquidations")
        return 0

    monkeypatch.setattr(db_session, "async_session_factory", lambda: FakeSessionContext())
    monkeypatch.setattr(StateShareService, "settle_daily_dividends", record_share_settlement)
    monkeypatch.setattr(BankruptcyService, "process_daily_liquidations", record_liquidations)
    scheduler = scheduler_module.scheduler
    scheduler.remove_all_jobs()
    monkeypatch.setattr(scheduler, "start", lambda: None)
    try:
        scheduler_module.setup_scheduler(object())
        job = scheduler.get_job("natbirzha_daily_settlement_job")
        assert job is not None
        asyncio.run(job.func())
    finally:
        scheduler.remove_all_jobs()
    assert calls == ["shares", "liquidations"]


def test_share_settlement_failure_does_not_skip_other_daily_jobs(monkeypatch) -> None:
    from backend.db import session as db_session
    from backend.natbirzha.services.bankruptcy_service import BankruptcyService
    from backend.natbirzha.services.state_share_service import StateShareService

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    calls: list[str] = []

    async def fail_share_settlement(_session):
        calls.append("shares")
        raise RuntimeError("simulated state-share ledger failure")

    async def record_liquidations(_session):
        calls.append("liquidations")
        return 0

    monkeypatch.setattr(db_session, "async_session_factory", lambda: FakeSessionContext())
    monkeypatch.setattr(StateShareService, "settle_daily_dividends", fail_share_settlement)
    monkeypatch.setattr(BankruptcyService, "process_daily_liquidations", record_liquidations)
    scheduler = scheduler_module.scheduler
    scheduler.remove_all_jobs()
    monkeypatch.setattr(scheduler, "start", lambda: None)
    try:
        scheduler_module.setup_scheduler(object())
        job = scheduler.get_job("natbirzha_daily_settlement_job")
        assert job is not None
        asyncio.run(job.func())
    finally:
        scheduler.remove_all_jobs()
    assert calls == ["shares", "liquidations"]


if __name__ == "__main__":
    from pytest import MonkeyPatch

    patch = MonkeyPatch()
    try:
        test_daily_financial_job_calls_state_share_settlement(patch)
    finally:
        patch.undo()
    print("NATBIRZHA state share scheduler checks: PASS")
