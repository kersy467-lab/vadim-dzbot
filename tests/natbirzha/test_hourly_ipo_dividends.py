"""Hourly IPO dividends are withheld from cash income and paid once per hour."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.stocks import (
    NatHourlyDividendAccrual,
    NatStock,
    NatStockHolding,
)
from backend.natbirzha.services.business_income_ledger_service import BusinessIncomeLedgerService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.npc_service import NPCReserveService


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


def test_unrealized_resource_output_is_not_dividend_income() -> None:
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
                NatInventory(company_id=issuer.id, item_id="energy", quantity=88),
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
            # Resource output is held as inventory, so producing it is not yet
            # cash income. Dividends start only when the goods are sold.
            expected_holdback = 0
            assert result["gross_cash"] == 0
            assert result["dividend_withheld_cash"] == expected_holdback
            assert result["net_cash"] == round(-result["maintenance_cash"], 2)
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


def test_a_company_receiving_another_ipo_dividend_withholds_its_own_share() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        hour_start = datetime(2026, 9, 24, 12)
        async with sessions() as session:
            source = NatCompany(user_id=951041, name="Dividend Source", specialization="miner", cash=1_000)
            public_holder = NatCompany(user_id=951042, name="Public Holder", specialization="miner", cash=500)
            final_holder = NatCompany(user_id=951043, name="Final Holder", specialization="miner", cash=300)
            session.add_all([source, public_holder, final_holder])
            await session.flush()
            source_stock = NatStock(
                company_id=source.id, total_shares=100, founder_shares=0,
                float_shares=100, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True, ipo_date=hour_start,
                dividend_eligible_from=hour_start, created_at=hour_start,
            )
            holder_stock = NatStock(
                company_id=public_holder.id, total_shares=100, founder_shares=0,
                float_shares=100, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True, ipo_date=hour_start,
                dividend_eligible_from=hour_start, created_at=hour_start,
            )
            session.add_all([source_stock, holder_stock])
            await session.flush()
            session.add_all([
                NatStockHolding(stock_id=source_stock.id, holder_company_id=public_holder.id,
                                shares_count=100, avg_price=10),
                NatStockHolding(stock_id=holder_stock.id, holder_company_id=final_holder.id,
                                shares_count=100, avg_price=10),
            ])
            await session.flush()
            await DividendService.accrue_cash_inflow(
                session, source, 100, now=hour_start + timedelta(minutes=15)
            )

            source_payout = await DividendService.settle_due_hourly(
                session, now=hour_start + timedelta(hours=1)
            )
            holder_accrual = await session.scalar(select(NatHourlyDividendAccrual).where(
                NatHourlyDividendAccrual.stock_id == holder_stock.id
            ))
            assert source_payout["total_paid"] == 10
            assert public_holder.cash == 509
            assert holder_accrual is not None
            assert holder_accrual.closed_profit == 10
            assert holder_accrual.dividend_pool == 1

            final_payout = await DividendService.settle_due_hourly(
                session, now=hour_start + timedelta(hours=2)
            )
            assert final_payout["total_paid"] == 1
            assert final_holder.cash == 301

        await engine.dispose()

    asyncio.run(run())


def test_ipo_company_withholds_dividends_from_npc_resource_sales() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 24, 12)
        async with sessions() as session:
            issuer = NatCompany(user_id=951051, name="NPC IPO Seller", specialization="miner", cash=1_000)
            session.add(issuer)
            await session.flush()
            stock = NatStock(
                company_id=issuer.id, total_shares=100, founder_shares=100,
                float_shares=0, current_price=10, last_valuation=1_000,
                dividend_rate_pct=10, is_listed=True, ipo_date=now,
                dividend_eligible_from=now, created_at=now,
            )
            session.add_all([
                stock,
                NatInventory(company_id=issuer.id, item_id="energy", quantity=1,
                             reserved_quantity=0, avg_cost_basis=0),
            ])
            await session.flush()

            sale = await NPCReserveService.execute_npc_trade(
                session, issuer, "energy", "SELL", 1
            )
            accrual = await session.scalar(select(NatHourlyDividendAccrual).where(
                NatHourlyDividendAccrual.stock_id == stock.id
            ))
            expected_holdback = round(sale["total_payout"] * 0.10, 2)

            assert sale["success"] is True
            assert accrual is not None
            assert accrual.closed_profit == sale["total_payout"]
            assert accrual.dividend_pool == expected_holdback
            assert issuer.cash == round(1_000 + sale["total_payout"] - expected_holdback, 2)

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_hourly_profit_splitting_respects_cutoff_and_hour_boundaries()
    test_ipo_dividend_pool_reconciles_hour_profit_and_pays_once()
    test_unrealized_resource_output_is_not_dividend_income()
    test_a_company_receiving_another_ipo_dividend_withholds_its_own_share()
    test_ipo_company_withholds_dividends_from_npc_resource_sales()
    print("NATBIRZHA hourly IPO dividends: PASS")
