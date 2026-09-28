"""Verify the half-hour liquidity endpoint serves persisted ranking snapshots."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api import liquidity_routes
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.liquidity import NatLiquiditySnapshot


def test_snapshot_response_includes_ranking_and_coverage(monkeypatch) -> None:
    async def check() -> None:
        now = datetime(2026, 9, 28, 12, 30)
        monkeypatch.setattr(liquidity_routes, "get_game_now", lambda: now)
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            session.add(NatLiquiditySnapshot(
                window_start=now - timedelta(hours=24),
                window_end=now,
                total_seller_cash_received=98,
                total_buyer_cash_paid=100,
                total_market_fees=2,
                sale_count=1,
                sectors_json={},
                unassigned_json={"by_item": {
                    "steel": {
                        "buyer_cash_paid": 100,
                        "seller_cash_received": 98,
                        "market_fees": 2,
                        "sale_count": 1,
                        "quantity": 10,
                    },
                }},
                coverage_json={"included_sources": ["market_trades"]},
            ))
            await session.flush()

            response = await liquidity_routes.get_market_liquidity(
                _company=NatCompany(id=1, user_id=1, name="Liquidity Test", specialization="miner"),
                session=session,
            )

            assert response["sale_count"] == 1
            assert response["items"][0]["item_id"] == "steel"
            assert response["items"][0]["buyer_cash_paid"] == 100
            assert response["coverage"] == {"included_sources": ["market_trades"]}

        await engine.dispose()

    asyncio.run(check())
