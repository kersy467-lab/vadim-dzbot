"""Delayed scheduler runs still honor the one-hour lifetime and two-order cap."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import game_dt_iso
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.services.city_order_service import CityOrderService


def test_late_issue_does_not_create_a_third_live_order() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with sessions() as session:
                user = User(tg_id=991599, full_name="City Schedule")
                session.add(user)
                await session.flush()
                session.add_all([
                    NatCompany(user_id=user.id, name="City Schedule Co", specialization="miner"),
                    NatStateTreasury(id=1, cash=100_000),
                ])
                await session.flush()
                start = datetime(2026, 9, 26, 12, 7)
                first = await CityOrderService.issue_due(session, now=start)
                second = await CityOrderService.issue_due(session, now=start + timedelta(minutes=28))
                delayed = await CityOrderService.issue_due(session, now=start + timedelta(minutes=55))
                assert first["created"] and second["created"]
                assert delayed["created"] is False and delayed["reason"] == "open_order_limit"
                assert await CityOrderService.count_open_orders(
                    session, now=start + timedelta(minutes=55)
                ) == 2
                next_slot = start + timedelta(minutes=88)
                third = await CityOrderService.issue_due(session, now=next_slot)
                assert third["created"] is True
                assert third["order"]["issued_at"] == game_dt_iso(next_slot)
                assert await CityOrderService.count_open_orders(session, now=next_slot) == 1
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(check())
