"""Hourly IPO dividends are withheld from hourly profit and paid once per hour."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.services.business_income_ledger_service import BusinessIncomeLedgerService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_hourly_profit_splitting_respects_cutoff_and_hour_boundaries() -> None:
    start = datetime(2026, 9, 24, 12, 30)
    parts = BusinessIncomeLedgerService.split_interval_by_hour(
        start,
        worked_hours=1,
        net_profit=120,
        eligible_after=start + timedelta(minutes=15),
    )

    assert parts == {
        datetime(2026, 9, 24, 12): 30,
        datetime(2026, 9, 24, 13): 60,
    }


def test_ipo_dividend_pool_reconciles_hour_profit_and_pays_once() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        hour_start = datetime(2026, 9, 24, 12)
        async with sessions() as session:
            issuer = NatCompany(user_id=951001, name="Hourly Issuer", specialization="miner", cash=1_000)
            holder = NatCompany(user_id=951002, name="Hourly Holder", specialization="miner", cash=500)
            session.add_all([issuer, holder])
            await session.flush()
            stock = NatStock(
                company_id=issuer.id,
                total_shares=100,
                founder_shares=0,
                float_shares=100,
                current_price=10,
                last_valuation=1_000,
                dividend_rate_pct=10,
                is_listed=True,
                ipo_date=hour_start,
                created_at=hour_start,
            )
            session.add(stock)
            await session.flush()
            session.add(NatStockHolding(
                stock_id=stock.id,
                holder_company_id=holder.id,
                shares_count=100,
                avg_price=10,
            ))
            await session.flush()

            first_holdback = await DividendService.accrue_hourly_profit(
                session, issuer, {hour_start: 100}, now=hour_start + timedelta(minutes=30)
            )
            correction = await DividendService.accrue_hourly_profit(
                session, issuer, {hour_start: -50}, now=hour_start + timedelta(minutes=45)
            )
            assert first_holdback == 10
            assert correction == -5

            paid = await DividendService.settle_due_hourly(
                session, now=hour_start + timedelta(hours=1)
            )
            assert paid["payment_count"] == 1
            assert paid["total_paid"] == 5
            assert holder.cash == 505

            replay = await DividendService.settle_due_hourly(
                session, now=hour_start + timedelta(hours=1)
            )
            assert replay["payment_count"] == 0
            assert holder.cash == 505

        await engine.dispose()

    asyncio.run(run())


def test_listed_company_withholds_hourly_profit_and_pays_at_hour_close() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        hour_start = datetime(2026, 9, 24, 12)
        spec = get_business_spec("coal_open_pit")
        async with sessions() as session:
            issuer = NatCompany(user_id=951011, name="Hourly Miner", specialization="miner", cash=1_000)
            holder = NatCompany(user_id=951012, name="Retail Investor", specialization="miner", cash=500)
            session.add_all([issuer, holder])
            await session.flush()
            business = NatBusiness(
                company_id=issuer.id,
                business_type=spec["id"],
                specialization="miner",
                stage=1,
                status="ACTIVE",
                capital_invested=spec["open_cost"],
                base_income_per_hour=spec["base_income_per_hour"],
                base_maintenance_per_hour=spec["base_maintenance_per_hour"],
                health=100,
                efficiency=1,
                metadata_json={"sale_mode": "NPC"},
                last_settled_at=hour_start,
            )
            session.add_all([
                business,
                NatInventory(company_id=issuer.id, item_id="energy", quantity=50),
                NatInventory(company_id=issuer.id, item_id="water", quantity=500),
                NatInventory(company_id=issuer.id, item_id="fuel_diesel", quantity=20),
                NatInventory(company_id=issuer.id, item_id="food", quantity=20),
            ])
            await session.flush()
            stock = NatStock(
                company_id=issuer.id,
                total_shares=200,
                founder_shares=100,
                float_shares=100,
                current_price=10,
                last_valuation=2_000,
                dividend_rate_pct=10,
                is_listed=True,
                ipo_date=hour_start,
                dividend_eligible_from=hour_start,
                created_at=hour_start,
            )
            session.add(stock)
            await session.flush()
            session.add(NatStockHolding(
                stock_id=stock.id,
                holder_company_id=holder.id,
                shares_count=100,
                avg_price=10,
            ))
            await session.flush()

            result = await IdleEconomyService.settle_company(
                session, issuer.id, now=hour_start + timedelta(hours=1)
            )
            operating_profit = round(result["gross_cash"] - result["maintenance_cash"], 2)
            expected_holdback = round(operating_profit * 0.10, 2)
            assert operating_profit > 0
            assert result["dividend_withheld_cash"] == expected_holdback
            assert result["net_cash"] == round(operating_profit - expected_holdback, 2)
            assert issuer.cash == round(1_000 + result["net_cash"], 2)
            assert holder.cash == 500

            payout = await DividendService.settle_due_hourly(
                session, now=hour_start + timedelta(hours=1)
            )
            investor_payout = round(expected_holdback / 2, 2)
            company_refund = round(expected_holdback - investor_payout, 2)
            assert payout["total_paid"] == investor_payout
            assert payout["total_refunded"] == company_refund
            assert holder.cash == round(500 + investor_payout, 2)
            assert issuer.cash == round(1_000 + result["net_cash"] + company_refund, 2)

        await engine.dispose()

    asyncio.run(run())
