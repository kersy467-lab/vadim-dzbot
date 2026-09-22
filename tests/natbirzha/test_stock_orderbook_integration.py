"""Database-level matching/escrow contract for the player stock order book."""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock, NatStockHolding, NatStockPriceSnapshot
from backend.natbirzha.services.stock_orderbook_service import StockOrderbookService


def test_two_sided_orderbook_matches_and_refunds_price_improvement() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 21, 10, 0)
        async with sessions() as session:
            issuer = NatCompany(user_id=81_001, name="Issuer", specialization="miner", cash=0)
            seller = NatCompany(user_id=81_002, name="Seller", specialization="agrarian", cash=0)
            buyer = NatCompany(user_id=81_003, name="Buyer", specialization="technoprom", cash=1_000)
            session.add_all([issuer, seller, buyer])
            await session.flush()
            stock = NatStock(
                company_id=issuer.id,
                total_shares=1_000,
                founder_shares=600,
                float_shares=400,
                current_price=10.0,
                last_valuation=10_000.0,
                dividend_rate_pct=5.0,
                is_listed=True,
                ipo_date=now,
                valuation_updated_at=now,
            )
            session.add(stock)
            await session.flush()
            session.add(NatStockHolding(
                stock_id=stock.id,
                holder_company_id=seller.id,
                shares_count=100,
                avg_price=8.0,
                updated_at=now,
            ))
            await session.commit()

            sell = await StockOrderbookService.place_limit_order(
                session, seller.id, stock.id, "SELL", 10, 10.0, now=now
            )
            assert sell["remaining"] == 10

            buy = await StockOrderbookService.place_limit_order(
                session, buyer.id, stock.id, "BUY", 7, 11.0, now=now
            )
            assert buy["status"] == "FILLED"
            assert buy["remaining"] == 0
            assert buy["trades"] == [{"quantity": 7, "price": 10.0, "total": 70.0}]

            await session.refresh(buyer)
            await session.refresh(seller)
            assert buyer.cash == 930.0  # 77 escrow, 7 refunded on price improvement.
            assert seller.cash == 70.0

            buyer_holding = await session.scalar(select(NatStockHolding).where(
                NatStockHolding.stock_id == stock.id,
                NatStockHolding.holder_company_id == buyer.id,
            ))
            seller_holding = await session.scalar(select(NatStockHolding).where(
                NatStockHolding.stock_id == stock.id,
                NatStockHolding.holder_company_id == seller.id,
            ))
            assert buyer_holding.shares_count == 7
            assert buyer_holding.avg_price == 10.0
            assert seller_holding.shares_count == 93

            book = await StockOrderbookService.orderbook(session, stock.id, buyer.id)
            assert book["best_ask"] == 10.0
            assert book["asks"][0]["quantity"] == 3
            assert book["best_bid"] is None
            snapshots = list((await session.execute(select(NatStockPriceSnapshot))).scalars().all())
            assert len(snapshots) == 1 and snapshots[0].price == 10.0

            pending = await StockOrderbookService.place_limit_order(
                session, buyer.id, stock.id, "BUY", 2, 9.0, now=now
            )
            assert pending["status"] == "ACTIVE"
            assert buyer.cash == 912.0
            cancelled = await StockOrderbookService.cancel_order(session, buyer.id, pending["order_id"], now=now)
            assert cancelled["status"] == "CANCELLED"
            await session.refresh(buyer)
            assert buyer.cash == 930.0

        await engine.dispose()

    asyncio.run(check())
