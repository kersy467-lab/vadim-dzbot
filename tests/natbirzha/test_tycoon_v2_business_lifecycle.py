"""Lifecycle mutations must settle first and be resistant to upgrade exploits."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_business_can_pause_resume_and_sell_but_not_during_upgrade() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_301, name="Lifecycle Corp", specialization="miner", cash=30_000)
            session.add(company)
            await session.flush()
            session.add_all([
                NatInventory(company_id=company.id, item_id="energy", quantity=88),
                NatInventory(company_id=company.id, item_id="water", quantity=100),
                NatInventory(company_id=company.id, item_id="fuel_diesel", quantity=2),
                NatInventory(company_id=company.id, item_id="food", quantity=1),
            ])
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
            business_id = opened["business"]["id"]

            paused = await BusinessService.pause(session, company.id, business_id, now=now)
            assert paused["status"] == "PAUSED_MANUAL"
            resumed = await BusinessService.resume(session, company.id, business_id, now=now + timedelta(hours=2))
            assert resumed["status"] == "ACTIVE"
            settled = await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=3))
            assert settled["net_cash"] == -8.4

            await BusinessService.start_upgrade(session, company.id, business_id, now=now + timedelta(hours=3))
            with pytest.raises(ValueError, match="улучшения"):
                await BusinessService.sell(session, company.id, business_id, now=now)

        await engine.dispose()

    asyncio.run(check())
