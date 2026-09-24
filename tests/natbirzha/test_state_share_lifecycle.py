"""Government-issued share lifecycle and Treasury dividend invariants."""

import asyncio
from datetime import date, datetime
from importlib.util import find_spec

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.state_shares import NatStateShare
from backend.natbirzha.models.stocks import NatHourlyDividendAccrual, NatStock


def test_state_share_service_lifecycle_and_global_dividend_proration() -> None:
    assert find_spec("backend.natbirzha.services.state_share_service") is not None, (
        "state share service must implement the approved Treasury-backed lifecycle"
    )
    from backend.natbirzha.models.state_shares import (
        NatStateShareDividendPayment,
        NatStateShareDailySettlement,
        NatStateShareHolding,
    )
    from backend.natbirzha.services.state_share_service import StateShareService

    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            first = NatCompany(user_id=931101, name="State Share One", specialization="miner", cash=10_000)
            second = NatCompany(user_id=931102, name="State Share Two", specialization="forester", cash=10_000)
            session.add_all([first, second])
            await session.flush()
            treasury = NatStateTreasury(id=1, cash=0)
            session.add(treasury)
            with pytest.raises(ValueError, match="finite"):
                await StateShareService.issue(
                    session, actor_id=777, title="NaN issue", purpose="invalid numeric check",
                    volume=10, issue_price=float("nan"), projected_annual_profit=100,
                    dividend_rate_pct=10, operation_key="issue:nan", commit=False,
                )
            with pytest.raises(ValueError, match="positive"):
                await StateShareService.issue(
                    session, actor_id=777, title="Rounded zero price", purpose="invalid price",
                    volume=10, issue_price=0.001, projected_annual_profit=100,
                    dividend_rate_pct=10, operation_key="issue:rounded-zero", commit=False,
                )
            issue = await StateShareService.issue(
                session,
                actor_id=777,
                title="National Infrastructure",
                purpose="Roads and utilities",
                volume=100,
                issue_price=5,
                projected_annual_profit=36_500,
                dividend_rate_pct=50,
                operation_key="issue:national-infrastructure",
                commit=False,
                now=datetime(2026, 9, 23, 12),
            )
            assert treasury.cash == 0, "issuing shares must not mint Treasury cash"
            assert (await StateShareService.list_shares(session))[0]["purpose"] == "Roads and utilities"

            first_buy = await StateShareService.buy(
                session, first, issue["share_id"], 25,
                operation_key="buy:one", commit=False,
            )
            assert await StateShareService.buy(
                session, first, issue["share_id"], 25,
                operation_key="buy:one", commit=False,
            ) == first_buy, "replaying a buy key must not charge twice"
            await StateShareService.buy(
                session, second, issue["share_id"], 75,
                operation_key="buy:two", commit=False,
            )
            assert first.cash == 9_875 and second.cash == 9_625
            assert treasury.cash == 500

            sale = await StateShareService.sell(
                session, first, issue["share_id"], 5,
                operation_key="sell:one", commit=False,
            )
            assert sale["total_proceeds"] == 25
            assert sale["remaining_volume"] == 5
            assert await StateShareService.sell(
                session, first, issue["share_id"], 5,
                operation_key="sell:one", commit=False,
            ) == sale
            assert first.cash == 9_900 and treasury.cash == 475

            treasury.cash = 0
            first_cash, holding_quantity, available_supply = first.cash, 20, 5
            with pytest.raises(ValueError, match="Treasury"):
                await StateShareService.sell(
                    session, first, issue["share_id"], 1,
                    operation_key="sell:insolvent", commit=False,
                )
            holding = await session.scalar(select(NatStateShareHolding).where(
                NatStateShareHolding.share_id == issue["share_id"],
                NatStateShareHolding.company_id == first.id,
            ))
            assert first.cash == first_cash and treasury.cash == 0
            assert holding.quantity == holding_quantity
            refreshed_issue = await session.get(NatStateShare, issue["share_id"])
            assert refreshed_issue.remaining_volume == available_supply

            # 95 held shares create 47.50 of daily obligations. With only 9.50
            # available, every holder receives exactly 20% of the formula amount.
            treasury.cash = 9.5
            ipo_at = datetime(2026, 9, 23, 12)
            session.add(NatStock(
                company_id=first.id, total_shares=100, founder_shares=100,
                float_shares=0, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True, ipo_date=ipo_at,
                dividend_eligible_from=ipo_at, created_at=ipo_at,
            ))
            await session.flush()
            settlement_date = date(2026, 9, 23)
            settled = await StateShareService.settle_daily_dividends(
                session, settlement_date=settlement_date, commit=False
            )
            assert settled["total_due"] == 47.5
            assert settled["total_paid"] == 9.5
            assert settled["proration_ratio"] == 0.2
            assert first.cash == 9_901.8 and second.cash == 9_632.5
            assert treasury.cash == 0
            cash_dividend_accrual = await session.scalar(select(NatHourlyDividendAccrual))
            assert cash_dividend_accrual is not None
            assert cash_dividend_accrual.closed_profit == 2
            assert cash_dividend_accrual.dividend_pool == 0.2

            replay = await StateShareService.settle_daily_dividends(
                session, settlement_date=settlement_date, commit=False
            )
            assert replay["status"] == "already_settled"
            assert first.cash == 9_901.8 and second.cash == 9_632.5
            assert await session.scalar(select(NatStateShareDailySettlement.id).where(
                NatStateShareDailySettlement.settlement_date == settlement_date
            )) is not None
            payments = (await session.execute(select(NatStateShareDividendPayment))).scalars().all()
            assert sorted(payment.amount_paid for payment in payments) == [2.0, 7.5]
            holdings = (await session.execute(select(NatStateShareHolding))).scalars().all()
            assert sorted(holding.quantity for holding in holdings) == [20, 75]

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_state_share_service_lifecycle_and_global_dividend_proration()
    print("NATBIRZHA state share lifecycle checks: PASS")
