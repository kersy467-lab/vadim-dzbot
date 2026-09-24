"""Configurable IPO terms and owner-managed dividend policy contracts."""

import asyncio
import os
import sys

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api.stock_routes import (
    IPOApplyRequest,
    DividendRateUpdateRequest,
    get_stocks_market,
)
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.stock_service import StockService


def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_ipo_accepts_custom_dividend_float_and_total_shares() -> None:
    async def check() -> None:
        engine, sessions = _session_factory()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(
                user_id=82_001, name="Custom IPO", specialization="miner", cash=100_000, level=18
            )
            session.add(company)
            await session.flush()

            stock = await StockService.apply_for_ipo(
                session,
                company,
                dividend_rate_pct=12.5,
                company_sale_pct=50,
                total_shares=4_000,
            )

            assert stock.total_shares == 4_000
            assert stock.float_shares == 2_000
            assert stock.founder_shares == 2_000
            assert stock.dividend_rate_pct == 12.5
            stock.float_shares = 1_000
            await session.commit()
            market = await get_stocks_market(session)
            listed_stock = next(row for row in market["stocks"] if row["stock_id"] == stock.id)
            assert listed_stock["float_shares"] == 1_000
            assert listed_stock["company_sale_pct"] == 50

            odd_share_company = NatCompany(
                user_id=82_005, name="Odd Share IPO", specialization="miner", cash=100_000, level=18
            )
            session.add(odd_share_company)
            await session.flush()
            odd_stock = await StockService.apply_for_ipo(
                session, odd_share_company, company_sale_pct=50, total_shares=4_001
            )
            assert odd_stock.float_shares == 2_000
            assert odd_stock.founder_shares == 2_001
            assert odd_stock.float_shares * 2 <= odd_stock.total_shares
        await engine.dispose()

    asyncio.run(check())


def test_ipo_rejects_share_count_below_four_thousand_and_float_above_half() -> None:
    async def check() -> None:
        engine, sessions = _session_factory()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(
                user_id=82_002, name="Invalid IPO", specialization="miner", cash=100_000, level=18
            )
            session.add(company)
            await session.flush()
            with pytest.raises(ValueError, match="share count"):
                await StockService.apply_for_ipo(
                    session, company, total_shares=3_999, company_sale_pct=40
                )
            with pytest.raises(ValueError, match="50%"):
                await StockService.apply_for_ipo(
                    session, company, total_shares=4_000, company_sale_pct=50.01
                )
            with pytest.raises(ValueError, match="0.1%"):
                await StockService.apply_for_ipo(
                    session, company, total_shares=4_000, company_sale_pct=0.05
                )
        await engine.dispose()

    asyncio.run(check())


def test_dividend_rate_can_be_raised_and_lowered_to_six_percent_only() -> None:
    async def check() -> None:
        engine, sessions = _session_factory()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(
                user_id=82_003, name="Dividend Policy", specialization="miner", cash=100_000, level=18
            )
            other_company = NatCompany(
                user_id=82_004, name="Not The Owner", specialization="miner", cash=100_000, level=18
            )
            session.add_all([company, other_company])
            await session.flush()
            stock = await StockService.apply_for_ipo(session, company, dividend_rate_pct=15)

            lowered = await StockService.set_dividend_rate(session, company, stock.id, 6)
            assert lowered.dividend_rate_pct == 6
            raised = await StockService.set_dividend_rate(session, company, stock.id, 30)
            assert raised.dividend_rate_pct == 30
            with pytest.raises(ValueError, match="6%"):
                await StockService.set_dividend_rate(session, company, stock.id, 5.99)
            with pytest.raises(ValueError, match="owner"):
                await StockService.set_dividend_rate(session, other_company, stock.id, 20)
        await engine.dispose()

    asyncio.run(check())


def test_ipo_api_validates_all_three_terms_and_update_floor() -> None:
    request = IPOApplyRequest(dividend_rate_pct=5, company_sale_pct=50, total_shares=4_000)
    assert request.dividend_rate_pct == 5
    assert request.company_sale_pct == 50
    assert request.total_shares == 4_000

    with pytest.raises(ValidationError):
        IPOApplyRequest(dividend_rate_pct=4.99, company_sale_pct=25, total_shares=4_000)
    with pytest.raises(ValidationError):
        IPOApplyRequest(dividend_rate_pct=10, company_sale_pct=50.1, total_shares=4_000)
    with pytest.raises(ValidationError):
        IPOApplyRequest(dividend_rate_pct=10, company_sale_pct=0.05, total_shares=4_000)
    with pytest.raises(ValidationError):
        IPOApplyRequest(dividend_rate_pct=10, company_sale_pct=25, total_shares=3_999)
    with pytest.raises(ValidationError):
        DividendRateUpdateRequest(dividend_rate_pct=5.99)


if __name__ == "__main__":
    for test in (
        test_ipo_accepts_custom_dividend_float_and_total_shares,
        test_ipo_rejects_share_count_below_four_thousand_and_float_above_half,
        test_dividend_rate_can_be_raised_and_lowered_to_six_percent_only,
        test_ipo_api_validates_all_three_terms_and_update_floor,
    ):
        test()
    print("IPO TERMS: ALL CHECKS PASSED")
