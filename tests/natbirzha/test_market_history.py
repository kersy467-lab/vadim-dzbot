"""Server history payloads used by the market charts."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api.stock_routes import get_stocks_market
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondListing, NatStateBond
from backend.natbirzha.models.instruments import NatReferenceRateSnapshot
from backend.natbirzha.models.market import NatMarketTrade
from backend.natbirzha.models.stocks import NatStock, NatStockPriceSnapshot
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.reference_instrument_service import ReferenceInstrumentService
from backend.natbirzha.services.state_bond_service import StateBondService


async def run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        now = datetime(2026, 9, 20, 12, 0, 0)
        for index, code in enumerate(("USD", "EUR", "GOLD", "SILVER")):
            session.add_all([
                NatReferenceRateSnapshot(
                    instrument_code=code, value_rub=90 + index, nominal=1,
                    source_id="cbr", source_url="test", quoted_at=now - timedelta(days=1),
                    fetched_at=now,
                ),
                NatReferenceRateSnapshot(
                    instrument_code=code, value_rub=91 + index, nominal=1,
                    source_id="cbr", source_url="test", quoted_at=now, fetched_at=now,
                ),
            ])
        company = NatCompany(user_id=991101, name="Chart Corp", specialization="miner")
        session.add(company)
        await session.flush()
        stock = NatStock(company_id=company.id, is_listed=True, current_price=12.5, last_valuation=125000)
        bond = NatStateBond(
            title="Chart Bond", total_volume=100, remaining_volume=90, face_value=100,
            coupon_rate=5, maturity_days=30, purpose="test", actor_id=1,
        )
        session.add_all([stock, bond])
        await session.flush()
        session.add_all([
            NatStockPriceSnapshot(stock_id=stock.id, price=10, valuation=100000, captured_at=now - timedelta(days=1)),
            NatStockPriceSnapshot(stock_id=stock.id, price=12.5, valuation=125000, captured_at=now),
            NatBondListing(
                operation_key="chart-listing", bond_id=bond.id, seller_company_id=company.id,
                quantity=1, unit_price=103, status="OPEN", created_at=now,
            ),
            NatMarketTrade(
                item_id="iron_ore", buyer_company_id=company.id, seller_company_id=company.id,
                price=34, quantity=5, total_amount=170, fee_amount=1,
                executed_at=now - timedelta(days=1),
            ),
            NatMarketTrade(
                item_id="iron_ore", buyer_company_id=company.id, seller_company_id=company.id,
                price=38, quantity=5, total_amount=190, fee_amount=1,
                executed_at=now,
            ),
        ])
        await session.commit()

        catalog = await ReferenceInstrumentService.catalog(session, now=now)
        assert len(catalog[0]["history"]) == 2
        stocks = await get_stocks_market(session=session)
        assert len(stocks["stocks"][0]["history"]) >= 2
        bonds = await StateBondService.list_bonds(session)
        assert bonds[0]["history"][0]["price"] == 103
        orderbook = await MarketService.get_orderbook(session, "iron_ore")
        assert [point["price"] for point in orderbook["history"]] == [34, 38]
    await engine.dispose()
    print("NATBIRZHA market history checks: PASS")


if __name__ == "__main__":
    asyncio.run(run())
