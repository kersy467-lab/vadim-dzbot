"""Portfolio history combines settled dividends and coupons into bounded payout rows."""

import asyncio
from datetime import date, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api.portfolio_routes import build_payout_history, get_unified_portfolio
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondSettlement, NatStateBond
from backend.natbirzha.models.state_shares import (
    NatStateShare,
    NatStateShareDailySettlement,
    NatStateShareDividendPayment,
)
from backend.natbirzha.models.stocks import (
    NatHourlyDividendAccrual,
    NatHourlyDividendPayment,
    NatStock,
)


def test_payout_history_aggregates_by_paid_hour_and_keeps_sold_bond_coupons() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            holder = NatCompany(user_id=98_001, name="History Holder", specialization="miner", cash=0)
            issuer = NatCompany(user_id=98_002, name="Hourly Issuer", specialization="metallurgist", cash=0)
            session.add_all([holder, issuer])
            await session.flush()

            sold_bond = NatStateBond(
                title="Старая облигация", total_volume=100, remaining_volume=0,
                face_value=100, coupon_rate=30, maturity_days=30,
                purpose="История должна сохраниться", actor_id=98_001,
            )
            another_bond = NatStateBond(
                title="Вторая облигация", total_volume=100, remaining_volume=0,
                face_value=100, coupon_rate=30, maturity_days=30,
                purpose="Тест агрегации", actor_id=98_001,
            )
            stock = NatStock(company_id=issuer.id, current_price=10, last_valuation=1000)
            share = NatStateShare(
                title="Энергетическая госакция", purpose="Тест", total_volume=10,
                remaining_volume=0, issue_price=100, projected_annual_profit=10,
                dividend_rate_pct=5, actor_id=98_001,
            )
            session.add_all([sold_bond, another_bond, stock, share])
            await session.flush()

            coupon_rows = [
                (sold_bond.id, "old-bond-minute-1", 1.25, datetime(2026, 9, 24, 10, 4)),
                (sold_bond.id, "old-bond-minute-2", 1.25, datetime(2026, 9, 24, 10, 44)),
                (another_bond.id, "other-bond-minute", 2.50, datetime(2026, 9, 24, 10, 59)),
                (sold_bond.id, "next-hour-minute", 1.50, datetime(2026, 9, 24, 11, 1)),
            ]
            session.add_all([
                NatBondSettlement(
                    operation_key=key, bond_id=bond_id, company_id=holder.id,
                    settlement_type="COUPON", period_number=1, entitled_quantity=10,
                    amount_rub=amount, status="PAID", due_at=paid_at, paid_at=paid_at,
                )
                for bond_id, key, amount, paid_at in coupon_rows
            ])
            session.add(NatBondSettlement(
                operation_key="unpaid-coupon", bond_id=sold_bond.id, company_id=holder.id,
                settlement_type="COUPON", period_number=2, entitled_quantity=10,
                amount_rub=999, status="PENDING", due_at=datetime(2026, 9, 24, 12),
            ))
            accrual = NatHourlyDividendAccrual(
                stock_id=stock.id, hour_start=datetime(2026, 9, 24, 9),
                closed_profit=100, dividend_rate_pct=10, dividend_pool=10, status="PAID",
                paid_at=datetime(2026, 9, 24, 10, 2),
            )
            daily_settlement = NatStateShareDailySettlement(
                operation_key="gov-share-settlement", settlement_date=date(2026, 9, 24),
                total_due=5, total_paid=5, proration_ratio=1,
                treasury_cash_before=1000, treasury_cash_after=995,
            )
            session.add_all([accrual, daily_settlement])
            await session.flush()
            session.add_all([
                NatHourlyDividendPayment(
                    accrual_id=accrual.id, stock_id=stock.id, holder_company_id=holder.id,
                    shares_count=100, payout_cash=7, hour_start=datetime(2026, 9, 24, 9),
                    paid_at=datetime(2026, 9, 24, 10, 2),
                ),
                NatStateShareDividendPayment(
                    operation_key="gov-share-payment", settlement_id=daily_settlement.id,
                    share_id=share.id, company_id=holder.id, quantity=10,
                    settlement_date=date(2026, 9, 24), amount_due=5, amount_paid=5,
                    paid_at=datetime(2026, 9, 24, 10, 5),
                ),
            ])
            await session.commit()

            rows = await build_payout_history(session, holder.id)
            bond_rows = [row for row in rows if row["kind"] == "bond_coupon"]
            assert len(bond_rows) == 2
            assert bond_rows[0]["paid_at"] == "2026-09-24T11:00:00"
            assert bond_rows[1]["paid_at"] == "2026-09-24T10:00:00"
            assert bond_rows[1]["payout_cash"] == 5.0
            assert "облигац" in bond_rows[1]["title"].lower()
            assert not any(row["payout_cash"] == 999 for row in rows)
            assert sum(row["payout_cash"] for row in rows if row["kind"] == "company_dividend") == 7
            assert sum(row["payout_cash"] for row in rows if row["kind"] == "state_share_dividend") == 5
            assert rows == sorted(rows, key=lambda row: row["paid_at"], reverse=True)

            portfolio = await get_unified_portfolio(holder, session)
            assert portfolio["payout_history"] == rows
            assert portfolio["summary"]["coupons_earned"] == 6.5

        await engine.dispose()

    asyncio.run(check())


def test_payout_history_is_bounded_after_sql_aggregation() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(user_id=98_003, name="Bounded History", specialization="miner", cash=0)
            session.add(company)
            await session.flush()
            bond = NatStateBond(
                title="Минутные купоны", total_volume=100, remaining_volume=0,
                face_value=100, coupon_rate=30, maturity_days=30,
                purpose="Bound test", actor_id=98_003,
            )
            session.add(bond)
            await session.flush()
            session.add_all([
                NatBondSettlement(
                    operation_key=f"bounded-{hour}-{minute}", bond_id=bond.id,
                    company_id=company.id, settlement_type="COUPON", period_number=1,
                    entitled_quantity=1, amount_rub=1, status="PAID",
                    due_at=datetime(2026, 9, 1, hour, minute),
                    paid_at=datetime(2026, 9, 1, hour, minute),
                )
                for hour in range(24) for minute in (0, 15, 30, 45)
            ])
            await session.commit()

            rows = await build_payout_history(session, company.id, limit=5)
            assert len(rows) == 5
            assert all(row["kind"] == "bond_coupon" for row in rows)
            assert all(row["payout_cash"] == 4 for row in rows)
            assert rows[0]["paid_at"] == "2026-09-01T23:00:00"
        await engine.dispose()

    asyncio.run(check())
