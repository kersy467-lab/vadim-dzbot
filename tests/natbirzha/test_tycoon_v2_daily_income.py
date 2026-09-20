"""Idle settlements feed a durable daily-profit source for IPO and dividends."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusinessIncomeDaily
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_idle_settlements_accumulate_business_daily_profit() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_401, name="Daily Ledger", specialization="retail", cash=20_000)
            session.add(company)
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "retail_chain", now=now)
            await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=1))
            await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=3))

            row = await session.scalar(select(NatBusinessIncomeDaily).where(
                NatBusinessIncomeDaily.business_id == opened["business"]["id"]
            ))
            assert row.gross_income == 660.0
            assert row.maintenance == 54.0
            assert row.net_profit == 606.0

        await engine.dispose()

    asyncio.run(check())
