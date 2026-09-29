"""State-bond coupons accrue every minute from the configured daily yield."""

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateBond, NatStateTreasury
from backend.natbirzha.models.tax import NatCompanyProfitPeriod, NatTaxPeriod
from backend.natbirzha.models.stocks import NatHourlyDividendAccrual, NatStock, NatStockHolding
from backend.natbirzha.services.state_bond_service import StateBondService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.tax_service import TaxService


def test_coupon_rate_of_30_percent_yields_15_percent_per_day() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        issued_at = datetime(2026, 9, 24, 12)
        async with sessions() as session:
            buyer = NatCompany(user_id=952001, name="Minute Bond Buyer", specialization="miner", cash=20_000)
            investor = NatCompany(user_id=952003, name="Bond Coupon Investor", specialization="miner", cash=5_000)
            session.add_all([buyer, investor])
            await session.flush()
            stock = NatStock(
                company_id=buyer.id, total_shares=100, founder_shares=0,
                float_shares=100, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True, ipo_date=issued_at,
                dividend_eligible_from=issued_at, created_at=issued_at,
            )
            session.add(stock)
            await session.flush()
            session.add(NatStockHolding(
                stock_id=stock.id, holder_company_id=investor.id,
                shares_count=100, avg_price=10,
            ))
            issue = await StateBondService.issue(
                session,
                actor_id=777,
                title="ОФЗ-Минута",
                volume=10,
                face_value=1_000,
                coupon_rate=30,
                maturity_days=30,
                purpose="minute coupon",
                now=issued_at,
                commit=False,
            )
            assert issue["next_coupon_at"] == (issued_at + timedelta(minutes=1)).isoformat()
            bond = await session.scalar(select(NatStateBond).where(NatStateBond.id == issue["bond_id"]))
            await StateBondService.buy(session, buyer, bond.id, 1, now=issued_at, commit=False)
            await session.commit()

        async with sessions() as session:
            first_tick = await StateBondService.settle_due(
                session, now=issued_at + timedelta(minutes=1)
            )
            one_minute = 1_000 * 0.15 / 1_440
            buyer_tax_period = await session.scalar(select(NatCompanyProfitPeriod).where(
                NatCompanyProfitPeriod.company_id == buyer.id
            ))
            assert buyer_tax_period is not None, "Received bond coupons must enter the company's net-profit ledger"
            assert buyer_tax_period.financial_income == round(one_minute, 6)
            # The first daily tax period closes at 11:00 UTC+5, 23 hours after issue.
            await TaxService.summary(session, buyer.id, now=issued_at + timedelta(hours=23))
            bond_tax = await session.scalar(select(NatTaxPeriod).where(NatTaxPeriod.company_id == buyer.id))
            assert bond_tax is not None
            assert bond_tax.taxable_profit == round(one_minute, 2)
            assert bond_tax.principal == round(round(one_minute, 2) * 0.13, 2)
            coupon_accrual = await session.scalar(select(NatHourlyDividendAccrual))
            assert first_tick["coupon_payments"] == 1
            assert first_tick["coupon_paid_rub"] == round(one_minute, 2)
            assert coupon_accrual is not None
            assert coupon_accrual.closed_profit == round(one_minute, 8)
            assert coupon_accrual.dividend_pool == 0.01
            refreshed_buyer = await session.get(NatCompany, buyer.id)
            assert refreshed_buyer.cash == round(19_000 + one_minute - 0.01, 8)

            paid_coupon_dividend = await DividendService.settle_due_hourly(
                session, now=issued_at + timedelta(hours=1)
            )
            assert paid_coupon_dividend["total_paid"] == 0.01
            refreshed_investor = await session.get(NatCompany, investor.id)
            assert refreshed_investor.cash == 5_000.01

            replay = await StateBondService.settle_due(
                session, now=issued_at + timedelta(minutes=1)
            )
            assert replay["coupon_payments"] == 0

            late_buyer = NatCompany(
                user_id=952002, name="Late Bond Buyer", specialization="miner", cash=20_000
            )
            session.add(late_buyer)
            await session.flush()
            await StateBondService.buy(
                session, late_buyer, bond.id, 1,
                now=issued_at + timedelta(minutes=2), commit=False,
            )
            # The elapsed minute is paid to the original holder before the new
            # buyer acquires the bond, so there is no backdated coupon.
            assert late_buyer.cash == 19_000

            catch_up = await StateBondService.settle_due(
                session, now=issued_at + timedelta(minutes=3)
            )
            assert catch_up["coupon_payments"] == 2
            assert catch_up["coupon_paid_rub"] == round(one_minute * 2, 2)

        await engine.dispose()

    asyncio.run(run())


def test_offline_coupon_catchup_batches_idempotency_lookups() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        issued_at = datetime(2026, 9, 24, 12)
        async with sessions() as session:
            company = NatCompany(
                user_id=952010, name="Offline Bond Buyer", specialization="miner", cash=10_000,
            )
            session.add(company)
            await session.flush()
            issue = await StateBondService.issue(
                session,
                actor_id=777,
                title="ОФЗ-Оффлайн",
                volume=2,
                face_value=100,
                coupon_rate=30,
                maturity_days=3,
                purpose="offline catch-up",
                now=issued_at,
                commit=False,
            )
            treasury = await session.scalar(select(NatStateTreasury))
            treasury.cash = 1_000_000
            bond = await session.get(NatStateBond, issue["bond_id"])
            await StateBondService.buy(session, company, bond.id, 1, now=issued_at, commit=False)
            await session.commit()

        lookup_queries = 0
        recipient_queries = 0

        def count_idempotency_lookups(_conn, _cursor, statement, _parameters, _context, _executemany):
            nonlocal lookup_queries, recipient_queries
            normalized = statement.lower()
            if "select nat_bond_settlements.id" in normalized and "operation_key" in normalized:
                lookup_queries += 1
            if "select nat_companies.id" in normalized and "from nat_companies" in normalized:
                recipient_queries += 1

        event.listen(engine.sync_engine, "before_cursor_execute", count_idempotency_lookups)
        try:
            async with sessions() as session:
                result = await StateBondService.settle_due(
                    session, now=issued_at + timedelta(minutes=5), commit=True,
                )
                assert result["coupon_payments"] == 5
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_idempotency_lookups)
            await engine.dispose()

        assert lookup_queries <= 1, f"Expected batched idempotency lookup, got {lookup_queries} minute queries"
        assert recipient_queries <= 1, f"Expected one recipient lookup, got {recipient_queries} per-coupon queries"

    asyncio.run(run())


def test_bond_scheduler_runs_each_minute() -> None:
    scheduler_path = Path(__file__).resolve().parents[2] / "backend" / "bot" / "services" / "scheduler.py"
    source = scheduler_path.read_text(encoding="utf-8")
    job = re.search(
        r"scheduler\.add_job\(\s*run_natbirzha_bond_settlement,\s*"
        r"trigger=CronTrigger\((.*?)\),\s*id=\"natbirzha_bond_settlement_job\"",
        source,
        re.DOTALL,
    )
    assert job and 'minute="*"' in job.group(1)
