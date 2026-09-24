"""Idle settlements feed a durable daily-profit source for IPO and dividends."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusinessIncomeDaily
from backend.natbirzha.models.inventory import NatInventory
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
            company = NatCompany(user_id=9_401, name="Daily Ledger", specialization="miner", cash=30_000)
            session.add(company)
            await session.flush()
            session.add_all([
                NatInventory(company_id=company.id, item_id="energy", quantity=264),
                NatInventory(company_id=company.id, item_id="water", quantity=12),
                NatInventory(company_id=company.id, item_id="fuel_diesel", quantity=6),
                NatInventory(company_id=company.id, item_id="food", quantity=3),
            ])
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
            await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=1))
            await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=3))

            row = await session.scalar(select(NatBusinessIncomeDaily).where(
                NatBusinessIncomeDaily.business_id == opened["business"]["id"]
            ))
            assert row.gross_income == 5032.95
            assert row.maintenance == 25.2
            assert row.net_profit == 5007.75

        await engine.dispose()

    asyncio.run(check())
