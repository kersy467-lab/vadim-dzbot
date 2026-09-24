"""IPO dividends follow received cash, regardless of the issuer's net profit."""

import asyncio
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.models.stocks import NatHourlyDividendAccrual, NatStock, NatStockHolding
from backend.natbirzha.services.dividend_service import DividendService


def test_multiple_cash_receipts_accumulate_into_one_hourly_dividend_pool() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        hour_start = get_game_now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        async with sessions() as session:
            issuer = NatCompany(user_id=951021, name="Cash Flow Issuer", specialization="miner", cash=1_000)
            holder = NatCompany(user_id=951022, name="Cash Flow Holder", specialization="miner", cash=500)
            session.add_all([issuer, holder])
            await session.flush()
            stock = NatStock(
                company_id=issuer.id, total_shares=100, founder_shares=0,
                float_shares=100, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True, ipo_date=hour_start,
                created_at=hour_start,
            )
            session.add(stock)
            await session.flush()
            session.add(NatStockHolding(
                stock_id=stock.id, holder_company_id=holder.id,
                shares_count=100, avg_price=10,
            ))
            await session.flush()

            first = await DividendService.accrue_cash_inflow(
                session, issuer, 100, now=hour_start + timedelta(minutes=10)
            )
            second = await DividendService.accrue_cash_inflow(
                session, issuer, 50, now=hour_start + timedelta(minutes=40)
            )
            accrual = await session.scalar(select(NatHourlyDividendAccrual))
            assert first == 10
            assert second == 5
            assert accrual is not None
            assert accrual.closed_profit == 150
            assert accrual.dividend_pool == 15

            paid = await DividendService.settle_due_hourly(
                session, now=hour_start + timedelta(hours=1)
            )
            assert paid["total_paid"] == 15
            assert holder.cash == 515

        await engine.dispose()

    asyncio.run(run())


def test_dividend_holdback_ignores_negative_daily_profit_and_issuer_balance() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        hour_start = get_game_now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        async with sessions() as session:
            issuer = NatCompany(user_id=951031, name="Loss Making Issuer", specialization="retail", cash=1_000)
            session.add(issuer)
            await session.flush()
            session.add(NatDailyFinancials(
                company_id=issuer.id, calendar_date=hour_start.date(),
                gross_revenue=20, opex=500, closed_profit=-480,
                developer_fee_paid=0,
            ))
            stock = NatStock(
                company_id=issuer.id, total_shares=100, founder_shares=0,
                float_shares=100, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True, ipo_date=hour_start,
                dividend_eligible_from=hour_start, created_at=hour_start,
            )
            session.add(stock)
            await session.flush()

            withheld = await DividendService.accrue_cash_inflow(
                session, issuer, 100, now=hour_start + timedelta(minutes=30)
            )
            accrual = await session.scalar(select(NatHourlyDividendAccrual))
            assert withheld == 10
            assert accrual is not None
            assert accrual.closed_profit == 100
            assert accrual.dividend_pool == 10
            assert issuer.cash == 1_000

        await engine.dispose()

    asyncio.run(run())
