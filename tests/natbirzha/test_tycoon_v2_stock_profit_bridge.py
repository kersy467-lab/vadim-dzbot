"""Listed companies must value and pay from the V2 business profit ledger."""

import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.stock_service import StockService


def test_stock_valuation_and_daily_dividend_use_idle_business_profit() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(user_id=9_501, name="Public Idle", specialization="retail", cash=100_000)
            session.add(company)
            await session.flush()
            business = NatBusiness(company_id=company.id, business_type="retail_chain")
            session.add(business)
            await session.flush()
            stock = NatStock(
                company_id=company.id, total_shares=100, founder_shares=100, float_shares=0,
                current_price=100, last_valuation=10_000, dividend_rate_pct=5, is_listed=True,
            )
            session.add(stock)
            await session.flush()
            session.add_all([
                NatStockHolding(stock_id=stock.id, holder_company_id=company.id, shares_count=100, avg_price=100),
                NatBusinessIncomeDaily(
                    business_id=business.id, date=date(2026, 9, 20), gross_income=1_000,
                    maintenance=0, salary=0, resource_cost=0, net_profit=1_000,
                ),
            ])
            await session.flush()

            valuation = await StockService.calculate_company_valuation(session, company)
            assert 230_000 < valuation < 250_000
            paid = await DividendService.settle_daily_dividends_for_stock(
                session, stock, settlement_date=date(2026, 9, 20)
            )
            assert paid["closed_profit"] == 1_000
            assert paid["dividend_pool"] == 50.0

        await engine.dispose()

    asyncio.run(check())
