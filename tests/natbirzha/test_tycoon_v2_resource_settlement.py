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
                NatInventory(company_id=1, item_id="fuel_diesel", quantity=10, avg_cost_basis=1.2),
                NatInventory(company_id=1, item_id="water", quantity=2, avg_cost_basis=2),
            ])
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "diesel_power_station", now=now)
            await BusinessService.configure_sale_mode(session, company.id, opened["business"]["id"], "HOLD")

            settled = await IdleEconomyService.settle_company(
                session, company.id, now=now + timedelta(hours=4)
            )
            fuel = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "fuel_diesel"))
            energy = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "energy"))
            business = await session.get(NatBusiness, opened["business"]["id"])

            assert settled["maintenance_cash"] == 16.0
            assert fuel.quantity == 0.0
            assert energy.quantity == 348.25
            assert business.status == "PAUSED_SUPPLY"

        await engine.dispose()

    asyncio.run(check())
