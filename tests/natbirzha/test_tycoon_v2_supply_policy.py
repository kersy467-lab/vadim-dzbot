"""Autoprocurement is opt-in and may only fill the configured stock target."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.business_assets import NatBusinessSupplyPolicy
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.supply_policy_service import SupplyPolicyService


def test_auto_npc_policy_restock_inputs_before_resource_settlement() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_201, name="Auto Supply", specialization="power_engineer", cash=40_000)
            session.add(company)
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "energy_company", now=now)
            await SupplyPolicyService.configure(
                session, opened["business"]["id"], "coal", mode="AUTO_NPC",
                min_hours_stock=1, target_hours_stock=4, max_unit_price=40, allow_state_reserve=True,
            )
            await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=1))

            business = await session.get(NatBusiness, opened["business"]["id"])
            coal = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "coal"))
            policy = await session.scalar(select(NatBusinessSupplyPolicy).where(NatBusinessSupplyPolicy.business_id == business.id))
            assert business.status == "ACTIVE"
            assert coal.quantity == 1.05
            assert policy.mode == "AUTO_NPC"
            assert company.cash == 27_927.5

        await engine.dispose()

    asyncio.run(check())
