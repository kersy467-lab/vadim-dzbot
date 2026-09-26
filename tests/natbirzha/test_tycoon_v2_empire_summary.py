"""Read-model contract for the NATBIRZHA 2.0 empire screen."""

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, get_npc_buy_price, get_npc_sell_price
from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.empire_summary_service import EmpireSummaryService


def test_empire_summary_exposes_current_business_economy() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 9, 20, 12, 0)
        async with sessions() as session:
            company = NatCompany(user_id=9_001, name="Summary Corp", specialization="miner", cash=30_000)
            session.add(company)
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)

            summary = await EmpireSummaryService.build(session, company.id, now=now)
            assert summary["progression"]["level"] == 1
            assert summary["progression"]["xp"] == 100
            assert summary["progression"]["next_level_xp"] == 150
            assert summary["progression"]["xp_to_next"] == 50
            assert summary["progression"]["level_progress_pct"] == 66.67
            assert summary["cash"] == 18_000.0
            assert summary["income_per_hour"] == 0.0
            assert summary["expenses_per_hour"] == 8.4
            assert summary["net_cash_per_hour"] == -8.4
            business_summary = summary["businesses"][0]
            reference_revenue = sum(
                quantity * CANONICAL_ITEMS[item_id]["base_price"]
                for item_id, quantity in business_summary["outputs_per_hour"].items()
            )
            reference_input_cost = sum(
                quantity * CANONICAL_ITEMS[item_id]["base_price"]
                for item_id, quantity in business_summary["inputs_per_hour"].items()
            )
            reference_profit = reference_revenue - reference_input_cost - business_summary["maintenance_per_hour"]
            expected_profit_after_tax = reference_profit - max(0.0, reference_profit) * nat_settings.TAX_RATE
            npc_revenue = sum(
                quantity * get_npc_buy_price(item_id)
                for item_id, quantity in business_summary["outputs_per_hour"].items()
            )
            npc_input_cost = sum(
                quantity * get_npc_sell_price(item_id)
                for item_id, quantity in business_summary["inputs_per_hour"].items()
            )
            npc_profit = npc_revenue - npc_input_cost - business_summary["maintenance_per_hour"]
            expected_npc_profit_after_tax = npc_profit - max(0.0, npc_profit) * nat_settings.TAX_RATE
            assert business_summary["estimated_profit_per_hour"] == round(expected_profit_after_tax, 2)
            assert business_summary["estimated_npc_profit_per_hour"] == round(expected_npc_profit_after_tax, 2)
            assert business_summary["estimated_profit_basis"] == "MARKET_REFERENCE_VALUE"
            assert summary["estimated_profit_per_hour"] == round(expected_profit_after_tax, 2)
            assert summary["estimated_npc_profit_per_hour"] == round(expected_npc_profit_after_tax, 2)
            assert summary["estimated_tax_rate_pct"] == round(nat_settings.TAX_RATE * 100, 2)
            assert summary["slots"] == {"used": 1, "max": 10, "free": 9}
            assert summary["businesses"][0]["id"] == opened["business"]["id"]
            assert summary["businesses"][0]["sale_mode"] == "HOLD"
            assert summary["businesses"][0]["next_upgrade"]["cost"] == 600.0

        await engine.dispose()

    asyncio.run(check())
