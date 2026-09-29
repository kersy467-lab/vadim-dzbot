"""Database-level matching/escrow contract for the player stock order book."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock, NatStockHolding, NatStockOrder, NatStockPriceSnapshot
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


def test_stale_sell_order_cannot_crash_stock_quote() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 29, 12, 0)
        async with sessions() as session:
            issuer = NatCompany(user_id=82_001, name="Issuer", specialization="miner", cash=0)
            seller = NatCompany(user_id=82_002, name="Seller", specialization="agrarian", cash=0)
            buyer = NatCompany(user_id=82_003, name="Buyer", specialization="technoprom", cash=10_000)
            session.add_all([issuer, seller, buyer])
            await session.flush()
            stock = NatStock(
                company_id=issuer.id, total_shares=1_000, founder_shares=600,
                float_shares=400, current_price=300.0, last_valuation=300_000.0,
                is_listed=True, valuation_updated_at=now,
            )
            stale_ask = NatStockOrder(
                stock_id=1, trader_company_id=seller.id, order_type="SELL",
                shares_count=100, remaining_shares=100, price=38.0,
                status="ACTIVE", created_at=now - timedelta(hours=1),
            )
            session.add(stock)
            await session.flush()
            stale_ask.stock_id = stock.id
            session.add_all([
                NatStockHolding(
                    stock_id=stock.id, holder_company_id=seller.id,
                    shares_count=100, avg_price=100.0, updated_at=now,
                ),
                stale_ask,
            ])
            await session.commit()

            result = await StockOrderbookService.place_limit_order(
                session, buyer.id, stock.id, "BUY", 1, 300.0, now=now
            )

            await session.refresh(stock)
            await session.refresh(stale_ask)
            assert result["trades"] == []
            assert stock.current_price == 300.0
            assert stale_ask.status == "CANCELLED"
            assert stale_ask.remaining_shares == 0

        await engine.dispose()

    asyncio.run(check())


def test_one_share_fill_does_not_set_the_stock_quote_to_its_execution_price() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 29, 12, 0)
        async with sessions() as session:
            issuer = NatCompany(user_id=82_011, name="Issuer", specialization="miner", cash=0)
            seller = NatCompany(user_id=82_012, name="Seller", specialization="agrarian", cash=0)
            buyer = NatCompany(user_id=82_013, name="Buyer", specialization="technoprom", cash=10_000)
            session.add_all([issuer, seller, buyer])
            await session.flush()
            stock = NatStock(
                company_id=issuer.id, total_shares=1_000, founder_shares=600,
                float_shares=400, current_price=300.0, last_valuation=300_000.0,
                is_listed=True, valuation_updated_at=now,
            )
            session.add(stock)
            await session.flush()
            session.add(NatStockHolding(
                stock_id=stock.id, holder_company_id=seller.id,
                shares_count=1, avg_price=200.0, updated_at=now,
            ))
            await session.commit()

            await StockOrderbookService.place_limit_order(
                session, seller.id, stock.id, "SELL", 1, 200.0, now=now
            )
            result = await StockOrderbookService.place_limit_order(
                session, buyer.id, stock.id, "BUY", 1, 200.0, now=now
            )

            await session.refresh(stock)
            assert result["trades"] == [{"quantity": 1, "price": 200.0, "total": 200.0}]
            assert stock.current_price == 300.0

        await engine.dispose()

    asyncio.run(check())




def test_stock_orderbook_exposes_same_owner_guard() -> None:
    from types import SimpleNamespace

    same_owner = getattr(StockOrderbookService, "_same_owner", None)
    assert callable(same_owner)
    assert same_owner(SimpleNamespace(user_id=55), SimpleNamespace(user_id=55))
    assert not same_owner(SimpleNamespace(user_id=55), SimpleNamespace(user_id=56))


def test_stock_quote_requires_consensus_and_scales_impact_to_trade_size() -> None:
    from backend.natbirzha.models import stocks as stock_models

    trade_model = getattr(stock_models, "NatStockTrade", None)
    assert trade_model is not None

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 29, 12, 0)
        async with sessions() as session:
            issuer = NatCompany(user_id=82_031, name="Issuer", specialization="miner", cash=0)
            seller = NatCompany(user_id=82_032, name="Seller", specialization="agrarian", cash=0)
            buyer = NatCompany(user_id=82_033, name="Buyer", specialization="technoprom", cash=10_000)
            counterparty_a = NatCompany(user_id=82_034, name="Counterparty A", specialization="chemical", cash=0)
            counterparty_b = NatCompany(user_id=82_035, name="Counterparty B", specialization="ai_data", cash=0)
            counterparty_c = NatCompany(user_id=82_036, name="Counterparty C", specialization="power_engineer", cash=0)
            counterparty_d = NatCompany(user_id=82_037, name="Counterparty D", specialization="agrarian", cash=0)
            session.add_all([
                issuer, seller, buyer, counterparty_a, counterparty_b,
                counterparty_c, counterparty_d,
            ])
            await session.flush()
            stock = NatStock(
                company_id=issuer.id, total_shares=1_000, founder_shares=600,
                float_shares=400, current_price=300.0, last_valuation=300_000.0,
                is_listed=True, valuation_updated_at=now,
            )
            session.add(stock)
            await session.flush()
            session.add_all([
                trade_model(
                    stock_id=stock.id,
                    buyer_company_id=counterparty_a.id,
                    seller_company_id=counterparty_b.id,
                    buyer_user_id=counterparty_a.user_id,
                    seller_user_id=counterparty_b.user_id,
                    shares_count=5,
                    price=200.0,
                    executed_at=now - timedelta(minutes=3),
                ),
                trade_model(
                    stock_id=stock.id,
                    buyer_company_id=counterparty_a.id,
                    seller_company_id=counterparty_b.id,
                    buyer_user_id=counterparty_a.user_id,
                    seller_user_id=counterparty_b.user_id,
                    shares_count=5,
                    price=200.0,
                    executed_at=now - timedelta(minutes=2),
                ),
                trade_model(
                    stock_id=stock.id,
                    buyer_company_id=counterparty_c.id,
                    seller_company_id=counterparty_d.id,
                    buyer_user_id=counterparty_c.user_id,
                    seller_user_id=counterparty_d.user_id,
                    shares_count=5,
                    price=200.0,
                    executed_at=now - timedelta(minutes=1),
                ),
                NatStockHolding(
                    stock_id=stock.id, holder_company_id=seller.id,
                    shares_count=1, avg_price=200.0, updated_at=now,
                ),
            ])
            await session.commit()

            await StockOrderbookService.place_limit_order(
                session, seller.id, stock.id, "SELL", 1, 200.0, now=now
            )
            result = await StockOrderbookService.place_limit_order(
                session, buyer.id, stock.id, "BUY", 1, 200.0, now=now
            )

            await session.refresh(stock)
            assert result["trades"] == [{"quantity": 1, "price": 200.0, "total": 200.0}]
            assert 299.0 < stock.current_price < 300.0

        await engine.dispose()

    asyncio.run(check())
