"""Lazy settlement rules for career NATBIRZHA 2.0 businesses."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


async def create_mining_business(session, *, cash: float = 100_000.0, last_settled_at: datetime) -> tuple[NatCompany, NatBusiness]:
    spec = get_business_spec("coal_open_pit")
    company = NatCompany(user_id=8_001, name="Idle Corp", specialization="miner", cash=cash)
    session.add(company)
    await session.flush()
    # Enough stock to make supply irrelevant to the settlement-clock tests.
    session.add_all([
        NatInventory(company_id=company.id, item_id="energy", quantity=2_000),
        NatInventory(company_id=company.id, item_id="water", quantity=1_000),
        NatInventory(company_id=company.id, item_id="fuel_diesel", quantity=500),
        NatInventory(company_id=company.id, item_id="food", quantity=250),
    ])
    business = NatBusiness(
        company_id=company.id,
        business_type=spec["id"],
        specialization="miner",
        stage=1,
        status="ACTIVE",
        capital_invested=spec["open_cost"],
        base_income_per_hour=spec["base_income_per_hour"],
        base_maintenance_per_hour=spec["base_maintenance_per_hour"],
        health=100.0,
        efficiency=1.0,
        metadata_json={"sale_mode": "NPC"},
        last_settled_at=last_settled_at,
    )
    session.add(business)
    await session.commit()
    return company, business


def expected_net_cash_per_hour(business: NatBusiness, *, upgrading: bool) -> float:
    spec = get_business_spec(business.business_type)
    rates = resource_business_rates(business, spec, upgrading=upgrading)
    return round(-rates.maintenance_per_hour, 2)


def test_idle_settlement_applies_once_and_stops_after_tax_grace() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_mining_business(session, last_settled_at=start)
            hourly = expected_net_cash_per_hour(business, upgrading=False)
            first = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert first["net_cash"] == hourly
            assert first["xp_gained"] == 20
            assert first["progression"]["xp"] == 20
            assert first["progression"]["xp_to_next"] == 130
            assert company.cash == round(100_000.0 + hourly, 2)
            assert company.xp == 20
            coal = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id, NatInventory.item_id == "coal"
            ))
            assert coal is not None and coal.quantity > 0
            assert business.last_settled_at == start + timedelta(hours=1)

            repeated = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert repeated["net_cash"] == 0.0

            # The closed 12-hour tax period gets 12 hours of grace. Production
            # may settle only through that deadline, even though the requested
            # offline window is longer.
            capped = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=50))
            assert 0.0 < capped["settled_hours"] <= 23.0
            assert capped["tax_blocked"] is True
            assert business.last_settled_at == start + timedelta(hours=50)

            blocked_repeat = await IdleEconomyService.settle_company(
                session, company.id, now=start + timedelta(hours=50)
            )
            assert blocked_repeat["settled_hours"] == 0.0
            assert blocked_repeat["net_cash"] == 0.0

        await engine.dispose()

    asyncio.run(check())


def test_idle_settlement_completes_upgrade_mid_window() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_mining_business(session, last_settled_at=start)
            business.status = "UPGRADING"
            business.upgrade_target_stage = 2
            business.upgrade_started_at = start
            business.upgrade_ready_at = start + timedelta(minutes=30)
            before = expected_net_cash_per_hour(business, upgrading=True)
            await session.commit()

            # Compute stage-2 active rate on a detached-like copy of the same row.
            business.stage = 2
            business.status = "ACTIVE"
            after = expected_net_cash_per_hour(business, upgrading=False)
            business.stage = 1
            business.status = "UPGRADING"
            await session.flush()

            settlement = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert settlement["net_cash"] == round((before + after) / 2, 2)
            assert settlement["xp_gained"] == 90  # one productive hour + stage-2 completion reward
            assert settlement["progression"]["xp"] == 90
            assert business.stage == 2
            assert business.status == "ACTIVE"
            assert business.upgrade_ready_at is None

        await engine.dispose()

    asyncio.run(check())


def test_idle_settlement_never_moves_a_business_clock_backwards() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_mining_business(session, last_settled_at=start)
            settlement = await IdleEconomyService.settle_company(session, company.id, now=start - timedelta(minutes=5))
            assert settlement["settled_hours"] == 0.0
            assert company.cash == 100_000.0
            assert business.last_settled_at == start

        await engine.dispose()

    asyncio.run(check())
