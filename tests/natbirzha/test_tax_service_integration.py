"""Database-level contract for the mandatory NATBIRZHA profit tax (12h cycle, 12h grace, 3% hourly simple penalty)."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomePeriod
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.services.tax_service import TaxService


def test_12h_tax_grace_period_no_penalty() -> None:
    """Tax inside the 12-hour grace period has principal due but zero penalty and is not blocked."""
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now().replace(microsecond=0)
        # Period ended 6 hours ago -> well within 12h grace period
        p_end = now - timedelta(hours=6)
        p_start = p_end - timedelta(hours=12)

        async with sessions() as session:
            company = NatCompany(
                user_id=77_001, name="Grace Corp", specialization="miner", cash=1_000.0
            )
            session.add(company)
            await session.flush()
            business = NatBusiness(
                company_id=company.id, business_type="coal_open_pit", specialization="miner",
                stage=1, status="ACTIVE", capital_invested=12_000,
                base_income_per_hour=0, base_maintenance_per_hour=0,
            )
            session.add(business)
            await session.flush()
            session.add(NatBusinessIncomePeriod(
                business_id=business.id, period_start=p_start, period_end=p_end,
                gross_income=1_000.0, maintenance=0.0, salary=0.0, resource_cost=0.0,
                net_profit=1_000.0,
            ))
            await session.commit()

            summary = await TaxService.summary(session, company.id, now=now)
            assert summary["principal_due"] == 130.0
            assert summary["penalty_due"] == 0.0
            assert summary["total_due"] == 130.0
            assert summary["blocked"] is False
            assert summary["hours_until_block"] == 6

        await engine.dispose()

    asyncio.run(check())


def test_overdue_tax_penalty_block_and_payment() -> None:
    """Overdue tax assesses simple +3%/hour penalty on principal, blocks production, and clears on payment."""
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now().replace(microsecond=0)
        # Period ended 22 hours ago -> 12h grace + 10h overdue
        p_end = now - timedelta(hours=22)
        p_start = p_end - timedelta(hours=12)

        async with sessions() as session:
            company = NatCompany(
                user_id=77_002, name="Overdue Corp", specialization="miner", cash=1_000.0
            )
            session.add(company)
            await session.flush()
            business = NatBusiness(
                company_id=company.id, business_type="coal_open_pit", specialization="miner",
                stage=1, status="ACTIVE", capital_invested=12_000,
                base_income_per_hour=0, base_maintenance_per_hour=0,
            )
            session.add(business)
            await session.flush()
            session.add(NatBusinessIncomePeriod(
                business_id=business.id, period_start=p_start, period_end=p_end,
                gross_income=1_000.0, maintenance=0.0, salary=0.0, resource_cost=0.0,
                net_profit=1_000.0,
            ))
            await session.commit()

            summary = await TaxService.summary(session, company.id, now=now)
            # Principal: 1000 * 13% = 130.0
            assert summary["principal_due"] == 130.0
            # Simple penalty: 130 * 3% * 10 hours = 39.0
            assert summary["penalty_due"] == 39.0
            assert summary["total_due"] == 169.0
            assert summary["blocked"] is True

            # Repeated call must not compound penalty
            repeated = await TaxService.summary(session, company.id, now=now)
            assert repeated["total_due"] == 169.0

            result = await TaxService.pay(session, company.id)
            assert result["paid_now"] == 169.0
            assert result["total_due"] == 0.0
            assert result["blocked"] is False
            assert result["cash"] == 831.0

            treasury = await session.scalar(select(NatStateTreasury))
            assert treasury is not None
            assert treasury.cash >= 169.0

        await engine.dispose()

    asyncio.run(check())
