"""IPO eligibility starts at company level 7 in V2."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.capital_plan_service import capital_plan_for_company, ipo_recommendation_level
from backend.natbirzha.services.stock_service import StockService


def test_legacy_ipo_gate_is_also_level_seven() -> None:
    original = (nat_settings.TYCOON_V2_ENABLED, nat_settings.IPO_MIN_LEVEL)
    try:
        nat_settings.TYCOON_V2_ENABLED = False
        nat_settings.IPO_MIN_LEVEL = 7
        assert ipo_recommendation_level() == 7
    finally:
        nat_settings.TYCOON_V2_ENABLED, nat_settings.IPO_MIN_LEVEL = original


def test_tycoon_ipo_unlocks_at_level_seven() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        original = (
            nat_settings.TYCOON_V2_ENABLED,
            nat_settings.TYCOON_V2_IPO_MIN_LEVEL,
            nat_settings.IPO_MIN_LEVEL,
        )
        nat_settings.TYCOON_V2_ENABLED = True
        nat_settings.TYCOON_V2_IPO_MIN_LEVEL = 7
        nat_settings.IPO_MIN_LEVEL = 7
        try:
            async with sessions() as session:
                company = NatCompany(user_id=9_601, name="Midgame IPO", specialization="retail", cash=10_000)
                company.level = 6
                session.add(company)
                await session.flush()
                plan = capital_plan_for_company(company, is_public=False)
                assert plan["state"] == "grow_first"
                assert plan["ipo_available_from_level"] == 7
                with pytest.raises(ValueError, match="7"):
                    await StockService.apply_for_ipo(session, company)

                company.level = 7
                assert capital_plan_for_company(company, is_public=False)["state"] == "ipo_recommended"
        finally:
            (nat_settings.TYCOON_V2_ENABLED,
             nat_settings.TYCOON_V2_IPO_MIN_LEVEL,
             nat_settings.IPO_MIN_LEVEL) = original
            await engine.dispose()

    asyncio.run(check())
