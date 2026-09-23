"""Timed, cash-priced expansion for the Tycoon V2 business capacity."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_capacity_service import BusinessCapacityService
from backend.natbirzha.services.business_service import BusinessService


def test_capacity_starts_at_ten_and_does_not_follow_level_or_territory() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            company = NatCompany(
                user_id=990001,
                name="Capacity Corp",
                specialization="logistics",
                level=60,
                territory_tiles=20,
                business_slot_capacity=10,
            )
            session.add(company)
            await session.flush()
            quote = BusinessCapacityService.quote(company, now=datetime(2026, 9, 24))
            assert quote["current_capacity"] == 10
            assert quote["target_capacity"] == 11
            assert quote["duration_hours"] == 6
            assert BusinessService.business_slot_limits(capacity=10, used=9) == {
                "used": 9, "max": 10, "free": 1,
            }
        await engine.dispose()

    asyncio.run(check())


def test_slot_expansion_charges_cash_and_uses_six_then_twelve_hour_timers() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime(2026, 9, 24, 10)
        async with sessions() as session:
            company = NatCompany(
                user_id=990002,
                name="Expansion Corp",
                specialization="logistics",
                cash=10_000_000,
                business_slot_capacity=10,
            )
            session.add(company)
            await session.flush()

            first = await BusinessCapacityService.expand(session, company.id, now=now)
            assert first["target_capacity"] == 11
            assert first["duration_hours"] == 6
            assert first["ready_at"] == (now + timedelta(hours=6)).isoformat()
            assert first["remaining_cash"] < 10_000_000
            assert BusinessCapacityService.quote(company, now=now)["current_capacity"] == 10

            second = await BusinessCapacityService.expand(
                session, company.id, now=now + timedelta(hours=6)
            )
            assert second["target_capacity"] == 12
            assert second["duration_hours"] == 12
            assert BusinessCapacityService.quote(
                company, now=now + timedelta(hours=6)
            )["current_capacity"] == 11

        await engine.dispose()

    asyncio.run(check())
