"""A rebirth quote keeps its announced 99% reset without multiplying new assets."""

from backend.natbirzha.services.rebirth_valuation import (
    anchored_rebirth_valuation,
    recover_rebirth_anchor,
)
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models import NatCompany, NatStock, NatStockPriceSnapshot
from backend.natbirzha.services.stock_service import StockService


def test_rebirth_growth_adds_new_fundamentals_without_old_scale_factor():
    anchor, baseline = recover_rebirth_anchor(
        first_price=10.0,
        total_shares=4_000,
        legacy_scale=0.8,
    )

    assert anchor == 40_000
    assert baseline == 50_000
    assert anchored_rebirth_valuation(
        raw_valuation=13_050_000,
        anchor=anchor,
        baseline=baseline,
    ) == 13_040_000


def test_rebirth_valuation_still_has_a_positive_company_floor_after_losses():
    assert anchored_rebirth_valuation(
        raw_valuation=10,
        anchor=80_000,
        baseline=100_000,
    ) == 50_000


def test_rebirth_with_invalid_legacy_scale_uses_fundamentals_as_baseline():
    anchor, baseline = recover_rebirth_anchor(
        first_price=25.0,
        total_shares=2_000,
        legacy_scale=0,
    )
    assert anchor == 50_000
    assert baseline == 50_000


def test_due_legacy_stock_refresh_recovers_anchor_instead_of_reapplying_old_scale():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        now = get_game_now()
        rebirth_at = now - timedelta(minutes=45)
        async with sessions() as session:
            user = User(id=992001, tg_id=992001, full_name="Rebirth stock")
            session.add(user)
            await session.flush()
            company = NatCompany(
                user_id=user.id, name="Rebirth stock", specialization="miner",
                rebirth_count=1, last_rebirth_at=rebirth_at,
            )
            session.add(company)
            await session.flush()
            stock = NatStock(
                company_id=company.id, total_shares=4_000, current_price=1_000,
                last_valuation=4_000_000, rebirth_valuation_scale=80,
                valuation_updated_at=rebirth_at, is_listed=True,
            )
            session.add(stock)
            await session.flush()
            session.add(NatStockPriceSnapshot(
                stock_id=stock.id, price=1_000, valuation=4_000_000,
                captured_at=rebirth_at,
            ))
            await session.flush()

            with patch.object(
                StockService, "calculate_company_valuation", new=AsyncMock(return_value=1_050_000)
            ):
                refreshed = await StockService.refresh_due_valuations(session, now=now)

            assert refreshed == 1
            assert stock.rebirth_valuation_anchor == 4_000_000
            assert stock.rebirth_base_valuation == 50_000
            assert stock.rebirth_valuation_scale == 1
            assert stock.last_valuation == 5_000_000
        await engine.dispose()

    asyncio.run(check())
