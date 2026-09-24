"""Autoprocurement is opt-in and may only fill the configured stock target."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.business_assets import NatBusinessSupplyPolicy
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.supply_policy_service import SupplyPolicyService


def test_auto_npc_policy_restock_inputs_before_resource_settlement() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_201, name="Auto Supply", specialization="power_engineer", cash=40_000, level=15)
            session.add(company)
            await session.flush()
            session.add(NatInventory(company_id=company.id, item_id="water", quantity=100.0))
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "diesel_power_station", now=now)
            await SupplyPolicyService.configure(
                session, opened["business"]["id"], "fuel_diesel", mode="AUTO_NPC",
                min_hours_stock=1, target_hours_stock=4, max_unit_price=200, allow_state_reserve=True,
            )
            await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=1))

            business = await session.get(NatBusiness, opened["business"]["id"])
            fuel = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "fuel_diesel"))
            policy = await session.scalar(select(NatBusinessSupplyPolicy).where(NatBusinessSupplyPolicy.business_id == business.id))
            assert business.status == "ACTIVE"
            assert fuel.quantity == 15.0
            assert policy.mode == "AUTO_NPC"
            assert company.cash > 0

        await engine.dispose()

    asyncio.run(check())


def test_automatic_market_freight_is_consumed_only_after_a_fill() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 20, 12, 0)
        async with sessions() as session:
            buyer = NatCompany(user_id=9_202, name="Freight Buyer", specialization="power_engineer", cash=50_000, level=15)
            seller = NatCompany(user_id=9_203, name="Freight Seller", specialization="miner", cash=0)
            session.add_all([buyer, seller])
            await session.flush()
            session.add_all([
                NatInventory(company_id=buyer.id, item_id="logistics_capacity", quantity=2.0),
                NatInventory(company_id=seller.id, item_id="fuel_diesel", quantity=0.01),
            ])
            await session.commit()

            opened = await BusinessService.open_business(session, buyer.id, "diesel_power_station", now=now)
            business_id = opened["business"]["id"]
            await SupplyPolicyService.configure(
                session, business_id, "fuel_diesel", mode="AUTO_MARKET",
                min_hours_stock=1, target_hours_stock=4, max_unit_price=200,
                allow_state_reserve=False,
            )
            await MarketService.create_order(
                session, seller, "SELL", "fuel_diesel", price=100, quantity=0.01, commit=False,
            )

            filled = await SupplyPolicyService.auto_procure(
                session, buyer, await session.get(NatBusiness, business_id),
                get_business_spec("diesel_power_station"),
            )
            market_fill = next(row for row in filled if row["source"] == "MARKET")
            assert market_fill["purchased"] == 0.01
            capacity = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == buyer.id,
                NatInventory.item_id == "logistics_capacity",
            ))
            assert capacity.quantity == 1.0
            assert capacity.reserved_quantity == 0.0

            no_fill = await SupplyPolicyService.auto_procure(
                session, buyer, await session.get(NatBusiness, business_id),
                get_business_spec("diesel_power_station"),
            )
            assert next(row for row in no_fill if row["source"] == "MARKET")["reason"] == "no_asks"
            await session.refresh(capacity)
            assert capacity.quantity == 1.0
            assert capacity.reserved_quantity == 0.0

            capacity.quantity = 0.0
            blocked = await SupplyPolicyService.auto_procure(
                session, buyer, await session.get(NatBusiness, business_id),
                get_business_spec("diesel_power_station"),
            )
            blocked_market = next(row for row in blocked if row["source"] == "MARKET")
            assert blocked_market["reason"] == "logistics_capacity"
            assert blocked_market["purchased"] == 0.0
            assert capacity.reserved_quantity == 0.0

        await engine.dispose()

    asyncio.run(check())


def test_market_npc_fallback_remains_available_without_freight() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 20, 12, 0)
        async with sessions() as session:
            buyer = NatCompany(user_id=9_204, name="Fallback Buyer", specialization="power_engineer", cash=50_000, level=15)
            session.add(buyer)
            await session.commit()
            opened = await BusinessService.open_business(session, buyer.id, "diesel_power_station", now=now)
            business_id = opened["business"]["id"]
            await SupplyPolicyService.configure(
                session, business_id, "fuel_diesel", mode="AUTO_MARKET_NPC",
                min_hours_stock=1, target_hours_stock=4, max_unit_price=None,
                allow_state_reserve=True,
            )

            results = await SupplyPolicyService.auto_procure(
                session, buyer, await session.get(NatBusiness, business_id),
                get_business_spec("diesel_power_station"),
            )
            market = next(row for row in results if row["source"] == "MARKET")
            state = next(row for row in results if row["source"] == "STATE")
            assert market["reason"] == "logistics_capacity"
            assert state["success"] is True
            assert await session.scalar(select(NatInventory).where(
                NatInventory.company_id == buyer.id,
                NatInventory.item_id == "logistics_capacity",
            )) is None

        await engine.dispose()

    asyncio.run(check())
