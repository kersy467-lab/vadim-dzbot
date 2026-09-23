import asyncio
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.models import Base
from backend.db.session import async_session_factory, engine
from backend.natbirzha.config import get_game_now, get_game_today
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.stock_service import StockService


async def run_checks():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        company = await CompanyService.create_company(
            session, 930001, "Dividend Policy Corp", "power_engineer"
        )
        company.level = 18
        stock = await StockService.apply_for_ipo(session, company)

        assert stock.dividend_rate_pct == 5.0
        assert stock.valuation_updated_at is not None

        custom_company = await CompanyService.create_company(
            session, 930002, "Custom Dividend Corp", "miner"
        )
        custom_company.level = 18
        custom_stock = await StockService.apply_for_ipo(
            session, custom_company, dividend_rate_pct=7.5
        )
        assert custom_stock.dividend_rate_pct == 7.5

        # Listed shares follow the audited company valuation every 10 minutes.
        base_price = custom_stock.current_price
        refresh_at = get_game_now()
        custom_stock.valuation_updated_at = refresh_at - timedelta(minutes=11)
        custom_company.cash += 2_000_000.0
        await session.commit()

        refreshed_count = await StockService.refresh_due_valuations(session, now=refresh_at)
        assert refreshed_count == 1
        assert custom_stock.current_price > base_price
        fair_price = custom_stock.last_valuation / custom_stock.total_shares
        assert fair_price * 0.75 - 0.01 <= custom_stock.current_price <= fair_price * 1.25 + 0.01, (
            fair_price, custom_stock.current_price
        )
        assert custom_stock.valuation_updated_at == refresh_at
        assert await StockService.refresh_due_valuations(
            session, now=refresh_at + timedelta(minutes=9)
        ) == 0

        too_low_company = await CompanyService.create_company(
            session, 930003, "Too Low Dividend Corp", "forester"
        )
        too_low_company.level = 18
        try:
            await StockService.apply_for_ipo(session, too_low_company, dividend_rate_pct=4.99)
            raise AssertionError("IPO must reject a dividend rate below 5%")
        except ValueError as exc:
            assert "dividend" in str(exc).lower()

        session.add(NatDailyFinancials(
            company_id=custom_company.id,
            calendar_date=get_game_today(),
            gross_revenue=10_000.0,
            opex=0.0,
            closed_profit=10_000.0,
            developer_fee_paid=0.0,
            created_at=get_game_now(),
        ))
        await session.commit()
        settlement = await DividendService.settle_daily_dividends_for_stock(
            session, custom_stock, get_game_today()
        )
        # Only the 60% founder stake is held until another company buys float.
        assert settlement["dividend_pool"] == 450.0

    print("STOCK MARKET RULES: ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(run_checks())
