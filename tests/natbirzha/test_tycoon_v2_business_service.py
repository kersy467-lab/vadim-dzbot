"""Server-side business opening and upgrade contracts for NATBIRZHA 2.0."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService


def test_business_open_and_upgrade_are_server_priced_and_timed() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=8_101, name="Tycoon Corp", specialization="retail", cash=50_000)
            session.add(company)
            await session.commit()

            opened = await BusinessService.open_business(session, company.id, "retail_chain", now=now)
            assert opened["open_cost"] == 8_000.0
            assert opened["remaining_cash"] == 42_000.0
            assert opened["business"]["stage"] == 1
            assert opened["slots"] == {"used": 1, "max": 3, "free": 2}

            upgrade = await BusinessService.start_upgrade(session, company.id, opened["business"]["id"], now=now)
            assert upgrade["cost"] == 2_000.0
            assert upgrade["target_stage"] == 2
            assert upgrade["ready_at"] == now + timedelta(minutes=3)
            assert upgrade["remaining_cash"] == 40_000.0

            with pytest.raises(ValueError, match="already in progress"):
                await BusinessService.start_upgrade(session, company.id, opened["business"]["id"], now=now)

        await engine.dispose()

    asyncio.run(check())


def test_business_slots_scale_by_company_level_and_territory() -> None:
    assert BusinessService.business_slot_limits(level=1, territory_tiles=4, used=0) == {"used": 0, "max": 3, "free": 3}
    assert BusinessService.business_slot_limits(level=30, territory_tiles=20, used=6) == {"used": 6, "max": 11, "free": 5}
