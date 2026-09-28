"""Small startup wiring checks for city-order schema and scheduled jobs."""

import asyncio
from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from backend.bot.services.city_order_scheduler import register_city_order_jobs
from backend.bot.services.city_order_scheduler import issue_city_order_slot
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.city_order_migration import migrate_city_orders
from backend.natbirzha.migrations import MIGRATIONS
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.city_order_service import CityOrderService
from backend.natbirzha.services.event_broadcaster import EventBroadcaster


def test_city_order_migration_creates_order_tables_after_company_schema() -> None:
    assert any(version == "natbirzha_v15_001_city_orders" for version, _ in MIGRATIONS)

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(lambda sync: NatCompany.__table__.create(sync))
                await migrate_city_orders(connection)
                names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
                assert {
                    "nat_city_orders", "nat_city_order_cycle_states", "nat_city_order_deliveries",
                } <= names
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_city_order_scheduler_registers_half_hour_issue_and_minute_expiry() -> None:
    class CaptureScheduler:
        jobs = []

        def add_job(self, function, **kwargs):
            self.jobs.append((function, kwargs))

    scheduler = CaptureScheduler()
    scheduler.jobs = []
    register_city_order_jobs(scheduler)
    jobs = {options["id"]: options for _function, options in scheduler.jobs}
    issue = jobs["natbirzha_city_order_issue_job"]
    expiry = jobs["natbirzha_city_order_expiry_job"]
    assert "minute='0,30'" in str(issue["trigger"])
    assert "minute='*'" in str(expiry["trigger"])
    assert all(job["replace_existing"] and job["coalesce"] and job["max_instances"] == 1
               for job in jobs.values())


def test_city_order_api_is_registered_on_the_natbirzha_router() -> None:
    paths = {route.path for route in natbirzha_router.routes}
    assert "/natbirzha/market/city-orders" in paths
    assert "/natbirzha/market/city-orders/{order_id}/deliver" in paths


def test_issued_city_order_is_broadcast_after_commit(monkeypatch) -> None:
    async def check() -> None:
        class FakeSession:
            committed = False

            async def commit(self) -> None:
                self.committed = True

        session = FakeSession()

        class FakeSessionFactory:
            def __call__(self):
                return self

            async def __aenter__(self):
                return session

            async def __aexit__(self, *_args):
                return False

        async def issue_due(_cls, _session, *, now):
            assert now == datetime(2026, 9, 28, 12, 0)
            return {
                "created": True,
                "expired_count": 0,
                "order": {
                    "industry_name": "ИИ",
                    "item_name": "Вычислительная мощность ИИ",
                    "quantity": 80,
                    "unit": "выч. ч",
                    "unit_price": 90,
                    "reserved_cash": 7_200,
                    "expires_at": "2026-09-28T13:00:00+05:00",
                },
            }

        messages = []

        async def send_message(text: str) -> bool:
            assert session.committed, "notification must not precede the order commit"
            messages.append(text)
            return True

        monkeypatch.setattr(
            "backend.db.session.async_session_factory", FakeSessionFactory()
        )
        monkeypatch.setattr(CityOrderService, "issue_due", classmethod(issue_due))
        monkeypatch.setattr(EventBroadcaster, "send_message", staticmethod(send_message))
        monkeypatch.setattr(
            "backend.natbirzha.config.get_game_now",
            lambda: datetime(2026, 9, 28, 12, 0),
        )

        await issue_city_order_slot()
        assert len(messages) == 1
        assert "Новый заказ города" in messages[0]
        assert "Вычислительная мощность ИИ" in messages[0]
        assert "90" in messages[0]
        assert "7 200" in messages[0]

    asyncio.run(check())
