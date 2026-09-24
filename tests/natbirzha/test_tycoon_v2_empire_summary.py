"""Read-model contract for the NATBIRZHA 2.0 empire screen."""

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.empire_summary_service import EmpireSummaryService


def test_empire_summary_exposes_current_business_economy() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 20, 12, 0)
        async with sessions() as session:
            company = NatCompany(user_id=9_001, name="Summary Corp", specialization="miner", cash=30_000)
            session.add(company)
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)

            summary = await EmpireSummaryService.build(session, company.id, now=now)
            assert summary["progression"]["level"] == 1
            assert summary["progression"]["xp"] == 100
            assert summary["progression"]["next_level_xp"] == 150
            assert summary["progression"]["xp_to_next"] == 50
            assert summary["progression"]["level_progress_pct"] == 66.67
            assert summary["cash"] == 18_000.0
            assert summary["income_per_hour"] == 0.0
            assert summary["expenses_per_hour"] == 8.4
            assert summary["net_cash_per_hour"] == -8.4
            assert summary["estimated_profit_per_hour"] == 1300.0
            assert summary["slots"] == {"used": 1, "max": 10, "free": 9}
            assert summary["businesses"][0]["id"] == opened["business"]["id"]
            assert summary["businesses"][0]["sale_mode"] == "HOLD"
            assert summary["businesses"][0]["next_upgrade"]["cost"] == 600.0

        await engine.dispose()

    asyncio.run(check())
