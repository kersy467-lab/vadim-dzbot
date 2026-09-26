"""Missing recipients must not consume prorated state-share dividends."""

import asyncio
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.state_shares import NatStateShareHolding
from backend.natbirzha.models.tax import NatCompanyProfitPeriod
from backend.natbirzha.services.state_share_service import StateShareService


def test_missing_dividend_recipient_is_filtered_before_proration() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=932101,
                name="Valid dividend recipient",
                specialization="miner",
                cash=100,
            )
            treasury = NatStateTreasury(id=1, cash=2)
            session.add_all([company, treasury])
            await session.flush()
            issue = await StateShareService.issue(
                session,
                actor_id=777,
                title="Recipient filtering",
                purpose="orphan recipient test",
                volume=100,
                issue_price=1,
                projected_annual_profit=3_650,
                dividend_rate_pct=100,
                operation_key="recipient-filter:issue",
                commit=False,
            )
            session.add_all([
                NatStateShareHolding(
                    share_id=issue["share_id"], company_id=company.id,
                    quantity=10, invested_cash=10, dividends_earned=0,
                ),
                NatStateShareHolding(
                    share_id=issue["share_id"], company_id=999_999,
                    quantity=10, invested_cash=10, dividends_earned=0,
                ),
            ])

            result = await StateShareService.settle_daily_dividends(
                session, settlement_date=date(2026, 9, 23), commit=False
            )
            assert result["total_due"] == 1
            assert result["total_paid"] == 1
            assert company.cash == 101
            assert treasury.cash == 1
            tax_period = await session.scalar(select(NatCompanyProfitPeriod).where(
                NatCompanyProfitPeriod.company_id == company.id
            ))
            assert tax_period is not None, "Received state-share dividends must enter the company's net-profit ledger"
            assert tax_period.financial_income == 1
            replay = await StateShareService.settle_daily_dividends(
                session, settlement_date=date(2026, 9, 23), commit=False
            )
            assert replay["status"] == "already_settled"
            assert tax_period.financial_income == 1

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_missing_dividend_recipient_is_filtered_before_proration()
    print("NATBIRZHA settlement recipient checks: PASS")
