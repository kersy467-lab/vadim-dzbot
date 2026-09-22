"""Database-level contract for the mandatory NATBIRZHA profit tax."""

import asyncio
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.services.tax_service import TaxService


def test_overdue_tax_penalty_block_and_payment() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        today = get_game_now().date()
        tax_day = today - timedelta(days=4)
        async with sessions() as session:
            company = NatCompany(
                user_id=77_001,
                name="Tax Corp",
                specialization="miner",
                cash=1_000.0,
            )
            session.add(company)
            await session.flush()
            business = NatBusiness(
                company_id=company.id,
                business_type="coal_open_pit",
                specialization="miner",
                stage=1,
                status="ACTIVE",
                capital_invested=12_000,
                base_income_per_hour=0,
                base_maintenance_per_hour=0,
            )
            session.add(business)
            await session.flush()
            session.add(NatBusinessIncomeDaily(
                business_id=business.id,
                date=tax_day,
                gross_income=1_000.0,
                maintenance=0.0,
                salary=0.0,
                resource_cost=0.0,
                net_profit=1_000.0,
            ))
            await session.commit()

            summary = await TaxService.summary(session, company.id, today=today)
            assert summary["principal_due"] == 130.0
            assert summary["penalty_due"] == 65.0
            assert summary["total_due"] == 195.0
            assert summary["blocked"] is True

            # Re-reading the same day must not compound or duplicate the penalty.
            repeated = await TaxService.summary(session, company.id, today=today)
            assert repeated["total_due"] == 195.0

            result = await TaxService.pay(session, company.id)
            assert result["paid_now"] == 195.0
            assert result["total_due"] == 0.0
            assert result["blocked"] is False
            assert result["cash"] == 805.0

            treasury = await session.scalar(select(NatStateTreasury))
            assert treasury is not None
            assert treasury.cash >= 195.0

        await engine.dispose()

    asyncio.run(check())
