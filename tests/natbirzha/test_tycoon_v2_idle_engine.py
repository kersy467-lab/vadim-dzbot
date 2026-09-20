"""Lazy settlement rules for the first cash-only NATBIRZHA 2.0 business."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


async def create_cash_business(session, *, cash: float = 1_000.0, last_settled_at: datetime) -> tuple[NatCompany, NatBusiness]:
    company = NatCompany(user_id=8_001, name="Idle Corp", specialization="retail", cash=cash)
    session.add(company)
    await session.flush()
    business = NatBusiness(
        company_id=company.id,
        business_type="retail_chain",
        stage=1,
        status="ACTIVE",
        capital_invested=8_000,
        base_income_per_hour=220,
        base_maintenance_per_hour=18,
        last_settled_at=last_settled_at,
    )
    session.add(business)
    await session.commit()
    return company, business


def test_idle_settlement_applies_one_hour_once_and_caps_offline_cash() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_cash_business(session, last_settled_at=start)
            first = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert first["net_cash"] == 202.0
            assert company.cash == 1_202.0
            assert business.last_settled_at == start + timedelta(hours=1)

            repeated = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert repeated["net_cash"] == 0.0
            assert company.cash == 1_202.0

            capped = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=73))
            assert capped["settled_hours"] == 24.0
            assert capped["net_cash"] == 4_848.0
            assert company.cash == 6_050.0

        await engine.dispose()

    asyncio.run(check())


def test_idle_settlement_completes_upgrade_in_the_middle_of_offline_time() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_cash_business(session, last_settled_at=start)
            business.status = "UPGRADING"
            business.upgrade_target_stage = 2
            business.upgrade_started_at = start
            business.upgrade_ready_at = start + timedelta(minutes=30)
            await session.commit()

            settlement = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            # Stage 1 nets 202/hour for 30 minutes; stage 2 nets 236.1/hour for 30 minutes.
            assert settlement["net_cash"] == 219.05
            assert company.cash == 1_219.05
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
            company, business = await create_cash_business(session, last_settled_at=start)
            settlement = await IdleEconomyService.settle_company(session, company.id, now=start - timedelta(minutes=5))
            assert settlement["settled_hours"] == 0.0
            assert company.cash == 1_000.0
            assert business.last_settled_at == start

        await engine.dispose()

    asyncio.run(check())
