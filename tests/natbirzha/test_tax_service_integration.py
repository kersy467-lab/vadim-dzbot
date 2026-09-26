"""Database-level contract for the mandatory NATBIRZHA profit tax (12h cycle, 13% net tax, 3% hourly simple penalty)."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import get_game_now
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.tax import NatCompanyProfitPeriod
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.sabotage_service import SabotageService
from backend.natbirzha.services.tax_service import TaxService


def test_tax_penalty_and_block_start_after_closed_12h_period() -> None:
    """After the 12-hour earning period closes, unpaid tax blocks production and incurs hourly penalties."""
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now().replace(microsecond=0)
        # Period ended 6 hours ago; no extra grace period is granted.
        p_end = now - timedelta(hours=6)
        p_start = p_end - timedelta(hours=12)

        async with sessions() as session:
            company = NatCompany(
                user_id=77_001, name="Grace Corp", specialization="miner", cash=1_000.0
            )
            session.add(company)
            await session.flush()
            session.add(NatCompanyProfitPeriod(
                company_id=company.id, period_start=p_start, period_end=p_end,
                realized_revenue=1_000.0,
            ))
            await session.commit()

            closed = await TaxService.summary(session, company.id, now=p_end)
            assert closed["principal_due"] == 130.0
            assert closed["penalty_due"] == 0.0
            assert closed["blocked"] is True

            summary = await TaxService.summary(session, company.id, now=now)
            assert summary["principal_due"] == 130.0
            assert summary["penalty_due"] == 23.4
            assert summary["total_due"] == 153.4
            assert summary["blocked"] is True
            assert summary["hours_until_block"] == 0

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
        # Period ended 22 hours ago -> 22 full overdue hours.
        p_end = now - timedelta(hours=22)
        p_start = p_end - timedelta(hours=12)

        async with sessions() as session:
            company = NatCompany(
                user_id=77_002, name="Overdue Corp", specialization="miner", cash=1_000.0
            )
            session.add(company)
            await session.flush()
            session.add(NatCompanyProfitPeriod(
                company_id=company.id, period_start=p_start, period_end=p_end,
                realized_revenue=1_000.0,
            ))
            await session.commit()

            summary = await TaxService.summary(session, company.id, now=now)
            # Principal: 1000 * 13% = 130.0
            assert summary["principal_due"] == 130.0
            # Simple penalty: 130 * 3% * 22 hours = 85.8
            assert summary["penalty_due"] == 85.8
            assert summary["total_due"] == 215.8
            assert summary["blocked"] is True

            # Repeated call must not compound penalty
            repeated = await TaxService.summary(session, company.id, now=now)
            assert repeated["total_due"] == 215.8

            result = await TaxService.pay(session, company.id)
            assert result["paid_now"] == 215.8
            assert result["total_due"] == 0.0
            assert result["blocked"] is False
            assert result["cash"] == 784.2

            treasury = await session.scalar(select(NatStateTreasury))
            assert treasury is not None
            assert treasury.cash >= 169.0

        await engine.dispose()

    asyncio.run(check())


def test_tax_uses_closed_period_net_profit_and_fixed_13_percent(monkeypatch) -> None:
    """Tax is 13% of company-wide net operating profit, assessed only after 12 hours."""
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        period_start = datetime(2026, 9, 25, 0, 0)
        period_end = period_start + timedelta(hours=12)
        async with sessions() as session:
            company = NatCompany(
                user_id=77_004, name="Net Profit Corp", specialization="miner", cash=10_000.0
            )
            session.add(company)
            await session.flush()
            # Company-wide net is (3000 revenue - 1320 maintenance - 600 COGS) = 1080.
            # Record the first 11 hours, then verify no tax is due before the 12h close.
            await CompanyProfitLedgerService.record_interval(
                session, company.id, period_start, 11,
                revenue=250 * 11, maintenance=110 * 11, cost_of_goods_sold=50 * 11,
            )

            before_close = await TaxService.summary(
                session, company.id, now=period_end - timedelta(minutes=1)
            )
            assert before_close["principal_due"] == 0.0

            await CompanyProfitLedgerService.record_interval(
                session, company.id, period_start + timedelta(hours=11), 1,
                revenue=250, maintenance=110, cost_of_goods_sold=50,
            )
            row = await session.scalar(select(NatCompanyProfitPeriod).where(
                NatCompanyProfitPeriod.company_id == company.id,
                NatCompanyProfitPeriod.period_start == period_start,
            ))
            assert row is not None and row.operating_profit == 1_080.0

            summary = await TaxService.summary(session, company.id, now=period_end)
            assert summary["rate_pct"] == 13.0
            assert summary["principal_due"] == 140.4
            liability = summary["liabilities"][0]
            assert liability["taxable_profit"] == 1080.0

        await engine.dispose()

    monkeypatch.setattr(SabotageService, "get_tax_rate", staticmethod(lambda: 0.25))
    asyncio.run(check())


def test_offline_settlement_keeps_production_before_tax_stop_deadline() -> None:
    """A late login settles work through the exact stop time, then discards later hours."""
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        period_start = datetime(2026, 9, 25, 0, 0)
        period_end = datetime(2026, 9, 25, 12, 0)
        stop_at = period_end
        settled_at = datetime(2026, 9, 25, 18, 0)
        work_started = datetime(2026, 9, 25, 9, 0)

        async with sessions() as session:
            company = NatCompany(
                user_id=77_003, name="Deadline Corp", specialization="miner", cash=1_000.0
            )
            session.add(company)
            await session.flush()
            spec = get_business_spec("coal_open_pit")
            assert spec is not None
            business = NatBusiness(
                company_id=company.id,
                business_type="coal_open_pit",
                specialization="miner",
                stage=1,
                status="ACTIVE",
                capital_invested=float(spec["open_cost"]),
                base_income_per_hour=0.0,
                base_maintenance_per_hour=float(spec["base_maintenance_per_hour"]),
                health=100.0,
                efficiency=1.0,
                metadata_json={"sale_mode": "HOLD"},
                last_settled_at=work_started,
            )
            session.add(business)
            session.add_all(
                NatInventory(
                    company_id=company.id,
                    item_id=item_id,
                    quantity=100_000.0,
                    avg_cost_basis=1.0,
                )
                for item_id in spec["inputs_per_hour"]
            )
            await session.flush()
            session.add(NatCompanyProfitPeriod(
                company_id=company.id,
                period_start=period_start,
                period_end=period_end,
                realized_revenue=1_000.0,
            ))
            await session.commit()

            result = await IdleEconomyService.settle_company(
                session, company.id, now=settled_at
            )

            assert result["tax_blocked"] is True
            assert result["settled_hours"] == 3.0
            assert result["gross_value"] > 0.0
            assert business.last_settled_at == settled_at

        await engine.dispose()

    asyncio.run(check())
