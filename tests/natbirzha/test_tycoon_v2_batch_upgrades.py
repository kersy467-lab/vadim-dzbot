"""Atomic batch upgrades for affordable idle businesses."""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.business_upgrade_batch_service import BusinessUpgradeBatchService


def test_batch_upgrade_starts_every_candidate_when_total_cash_is_enough() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=12_001, name="Batch Corp", specialization="miner", cash=100_000)
            session.add(company)
            await session.commit()
            await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
            await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)

            result = await BusinessUpgradeBatchService.start_all(session, company.id, now=now)
            businesses = list((await session.scalars(
                select(NatBusiness).where(NatBusiness.company_id == company.id).order_by(NatBusiness.id)
            )).all())

            assert result["started_count"] == 2
            assert result["total_cost"] == 1_200.0
            assert result["remaining_cash"] == 74_800.0
            assert [business.status for business in businesses] == ["UPGRADING", "UPGRADING"]

        await engine.dispose()

    asyncio.run(check())


def test_batch_upgrade_starts_nothing_when_total_cash_is_short() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=12_002, name="Short Cash Corp", specialization="miner", cash=100_000)
            session.add(company)
            await session.commit()
            await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
            await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
            company.cash = 1_000
            await session.flush()

            with pytest.raises(ValueError, match="Недостаточно средств"):
                await BusinessUpgradeBatchService.start_all(session, company.id, now=now)

            businesses = list((await session.scalars(
                select(NatBusiness).where(NatBusiness.company_id == company.id).order_by(NatBusiness.id)
            )).all())
            assert company.cash == 1_000
            assert [(business.stage, business.status) for business in businesses] == [
                (1, "ACTIVE"), (1, "ACTIVE")
            ]

        await engine.dispose()

    asyncio.run(check())
