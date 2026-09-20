"""Resource businesses must consume inputs continuously and pause honestly."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_resource_business_consumes_inputs_and_pauses_when_supply_ends() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_101, name="Energy Corp", specialization="power_engineer", cash=40_000)
            session.add_all([
                company,
                NatInventory(company_id=1, item_id="coal", quantity=0.7, avg_cost_basis=30),
            ])
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "energy_company", now=now)

            settled = await IdleEconomyService.settle_company(
                session, company.id, now=now + timedelta(hours=4)
            )
            coal = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "coal"))
            energy = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "energy"))
            business = await session.get(NatBusiness, opened["business"]["id"])

            assert settled["maintenance_cash"] == 40.0
            assert coal.quantity == 0.0
            assert energy.quantity == 16.0
            assert business.status == "PAUSED_SUPPLY"

        await engine.dispose()

    asyncio.run(check())
