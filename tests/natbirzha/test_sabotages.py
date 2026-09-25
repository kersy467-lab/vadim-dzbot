"""Comprehensive tests for Natbirzha economic sabotages and crisis events."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock
from backend.natbirzha.models.inventory import get_item_base_price, get_npc_buy_price
from backend.natbirzha.catalogs.sabotages import SABOTAGES_CATALOG, get_sabotage_spec
from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.sabotage_service import SabotageService
from backend.natbirzha.services.state_credit_service import StateCreditService



def test_sabotages_catalog_completeness():
    """Verify that all 17 crisis events (12 base + 3 loss + 2 profit) are fully defined."""
    required_ids = [
        "key_rate",
        "military_operation",
        "state_default",
        "energy_crisis",
        "fuel_crisis",
        "water_shortage",
        "logistics_disruption",
        "state_construction",
        "commodity_boom",
        "tech_deficit",
        "bad_harvest",
        "deforestation_ban",
        # 3 new losses for all:
        "hyperinflation",
        "national_sanctions",
        "infrastructure_collapse",
        # 2 new profits for all:
        "economic_boom",
        "state_subsidies",
    ]
    assert len(SABOTAGES_CATALOG) == 17
    for sab_id in required_ids:
        assert sab_id in SABOTAGES_CATALOG
        spec = get_sabotage_spec(sab_id)
        assert spec is not None
        assert spec["name"]
        assert spec["icon"]
        assert spec["description"]
        assert spec["duration_hours"] in (12, 18, 24, 48)


def test_two_concurrent_sabotages_and_compounded_multipliers():
    """Test starting 2 simultaneous sabotages, compounded effects, and 2-limit constraint."""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 25, 10, 0, 0)

            # Initially no active sabotage
            actives = await SabotageService.get_active_sabotages(session, now=now)
            assert len(actives) == 0
            assert SabotageService.get_income_multiplier("oilman") == 1.0

            # 1. Start fuel_crisis (oilman +30%, logistics -25%, others 1.0, fuel_diesel +50%)
            res1 = await SabotageService.start_sabotage(
                session, sabotage_id="fuel_crisis", actor_id=101, now=now
            )
            assert res1["success"] is True
            assert res1["active_count"] == 1

            actives = await SabotageService.get_active_sabotages(session, now=now)
            assert len(actives) == 1
            assert SabotageService.get_income_multiplier("oilman") == 1.30
            # logistics now 0.70 (fuel_crisis income_multiplier, overrides other_income_mult 0.85)
            assert SabotageService.get_income_multiplier("logistics") == 0.70
            # miner has no specific multiplier -> gets other_income_mult = 0.85
            assert SabotageService.get_income_multiplier("miner") == 0.85
            base_diesel = get_item_base_price("fuel_diesel")
            assert base_diesel == round(1.2 * 1.50, 2)

            # 2. Start economic_boom as 2nd sabotage (all incomes +30%, credit -5%, bond 1.10)
            res2 = await SabotageService.start_sabotage(
                session, sabotage_id="economic_boom", actor_id=101, now=now
            )
            assert res2["success"] is True
            assert res2["active_count"] == 2

            actives = await SabotageService.get_active_sabotages(session, now=now)
            assert len(actives) == 2

            # Compounded income multipliers with economic_boom (other_income_mult=1.30):
            # oilman: 1.30 (fuel_crisis) * 1.30 (boom) = 1.69
            # logistics: 0.70 (fuel_crisis explicit) * 1.30 (boom) = 0.91
            # miner: 0.85 (fuel_crisis other) * 1.30 (boom) = 1.105
            assert SabotageService.get_income_multiplier("oilman") == 1.69
            assert SabotageService.get_income_multiplier("logistics") == round(0.70 * 1.30, 4)
            assert SabotageService.get_income_multiplier("miner") == round(0.85 * 1.30, 4)


            # Additive credit rate delta: 0.0 + (-0.05) = -0.05
            assert SabotageService.get_credit_rate_delta() == -0.05
            # Compounded bond price: 1.0 * 1.10 = 1.10
            assert SabotageService.get_bond_price_multiplier() == 1.10

            # Summary should contain 2 sabotages
            summary = SabotageService.get_active_summary()
            assert summary is not None
            assert summary["active"] is True
            assert summary["count"] == 2
            assert len(summary["sabotages"]) == 2

            # 3. Attempting to start a 3rd sabotage must fail (MAX = 2)
            try:
                await SabotageService.start_sabotage(
                    session, sabotage_id="water_shortage", actor_id=101, now=now
                )
            except ValueError as exc:
                assert "Уже активны 2 саботажа" in str(exc)
            else:
                raise AssertionError("Should not allow 3 active sabotages simultaneously")

            # 4. Attempting to start a duplicate sabotage must fail
            try:
                await SabotageService.start_sabotage(
                    session, sabotage_id="fuel_crisis", actor_id=101, now=now
                )
            except ValueError as exc:
                assert "активен" in str(exc).lower()
            else:
                raise AssertionError("Should not allow starting duplicate sabotage")

            # 5. Stop fuel_crisis individually
            stop_res = await SabotageService.stop_sabotage(
                session, actor_id=101, sabotage_id="fuel_crisis", reason="TEST_STOP", now=now
            )
            assert stop_res["success"] is True
            assert stop_res["remaining_active_count"] == 1

            actives = await SabotageService.get_active_sabotages(session, now=now)
            assert len(actives) == 1
            assert actives[0].sabotage_id == "economic_boom"

            # Multipliers now reflect only economic_boom (+30% all)
            assert SabotageService.get_income_multiplier("oilman") == 1.30
            assert SabotageService.get_income_multiplier("logistics") == 1.30
            assert SabotageService.get_income_multiplier("miner") == 1.30
            assert get_item_base_price("fuel_diesel") == 1.2  # diesel bonus removed

            # 6. Stop economic_boom
            stop_res2 = await SabotageService.stop_sabotage(
                session, actor_id=101, sabotage_id="economic_boom", reason="TEST_STOP", now=now
            )
            assert stop_res2["success"] is True
            assert stop_res2["remaining_active_count"] == 0

            actives = await SabotageService.get_active_sabotages(session, now=now)
            assert len(actives) == 0
            assert SabotageService.get_income_multiplier("oilman") == 1.0
            assert SabotageService.get_income_multiplier("logistics") == 1.0
            assert SabotageService.get_credit_rate_delta() == 0.0

        await engine.dispose()

    asyncio.run(run())


def test_stock_shock_positive_and_negative():
    """Test stock price shock both downward and upward (+15% economic_boom, -30% state_default)."""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=999, name="Public Giant", specialization="miner",
                cash=50_000, territory_tiles=4
            )
            session.add(company)
            await session.flush()

            stock = NatStock(
                company_id=company.id,
                total_shares=10_000,
                founder_shares=6_000,
                float_shares=4_000,
                current_price=100.0,
                last_valuation=1_000_000.0,
                is_listed=True,
            )
            session.add(stock)
            await session.commit()

            now = datetime(2026, 9, 25, 12, 0, 0)

            # 1. Economic boom shock (+15%)
            res = await SabotageService.start_sabotage(
                session, sabotage_id="economic_boom", actor_id=7755842535, now=now
            )
            assert res["success"] is True
            assert res["affected_stocks"] == 1
            await session.refresh(stock)
            assert stock.current_price == 115.0  # +15%
            assert stock.last_valuation == 1_150_000.0

            # Stop boom
            await SabotageService.stop_sabotage(session, actor_id=7755842535, sabotage_id="economic_boom", now=now)

            # 2. State default shock (-30%)
            res_def = await SabotageService.start_sabotage(
                session, sabotage_id="state_default", actor_id=7755842535, now=now
            )
            assert res_def["success"] is True
            await session.refresh(stock)
            assert stock.current_price == 80.5  # 115.0 * 0.70 = 80.5

            # Verify default blocks
            assert SabotageService.are_dividends_blocked() is True
            assert SabotageService.are_new_credits_blocked() is True

            await SabotageService.stop_sabotage(session, actor_id=7755842535, sabotage_id="state_default", now=now)
            assert SabotageService.are_dividends_blocked() is False
            assert SabotageService.are_new_credits_blocked() is False

        await engine.dispose()

    asyncio.run(run())


def test_loss_for_all_crises():
    """Verify hyperinflation and infrastructure_collapse hurt all businesses."""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 25, 15, 0, 0)

            # Hyperinflation: -25% to all businesses (other_income_mult=0.75), credit rate +15%
            await SabotageService.start_sabotage(
                session, sabotage_id="hyperinflation", actor_id=1, now=now
            )
            assert SabotageService.get_income_multiplier("oilman") == 0.75
            assert SabotageService.get_income_multiplier("miner") == 0.75
            assert SabotageService.get_income_multiplier("technoprom") == 0.75
            assert SabotageService.get_income_multiplier("agrarian") == 0.75
            assert SabotageService.get_credit_rate_delta() == 0.15

            await SabotageService.stop_sabotage(session, actor_id=1, sabotage_id="hyperinflation", now=now)
            assert SabotageService.get_income_multiplier("miner") == 1.0

            # Infrastructure collapse: -30% to all businesses, dividends frozen
            await SabotageService.start_sabotage(
                session, sabotage_id="infrastructure_collapse", actor_id=1, now=now
            )
            assert SabotageService.get_income_multiplier("miner") == 0.70
            assert SabotageService.are_dividends_blocked() is True

            await SabotageService.stop_sabotage(session, actor_id=1, sabotage_id="infrastructure_collapse", now=now)
            assert SabotageService.are_dividends_blocked() is False

def test_sabotage_tax_rates():
    """Verify national_sanctions (+10% tax -> 23%) and infrastructure_collapse (+5% tax -> 18%)."""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 25, 16, 0, 0)
            assert SabotageService.get_tax_rate() == 0.13
            assert SabotageService.get_tax_rate_delta() == 0.0

            # 1. National sanctions (+10% -> 23%)
            await SabotageService.start_sabotage(
                session, sabotage_id="national_sanctions", actor_id=1, now=now
            )
            assert SabotageService.get_tax_rate_delta() == 0.10
            assert SabotageService.get_tax_rate() == 0.23

            # 2. Add infrastructure_collapse (+5% -> total +15% -> 28%)
            await SabotageService.start_sabotage(
                session, sabotage_id="infrastructure_collapse", actor_id=1, now=now
            )
            assert SabotageService.get_tax_rate_delta() == 0.15
            assert SabotageService.get_tax_rate() == 0.28

            # 3. Stop national_sanctions (only infrastructure_collapse remains -> 18%)
            await SabotageService.stop_sabotage(
                session, actor_id=1, sabotage_id="national_sanctions", now=now
            )
            assert SabotageService.get_tax_rate_delta() == 0.05
            assert SabotageService.get_tax_rate() == 0.18

            # 4. Stop infrastructure_collapse (back to 13%)
            await SabotageService.stop_sabotage(
                session, actor_id=1, sabotage_id="infrastructure_collapse", now=now
            )
            assert SabotageService.get_tax_rate_delta() == 0.0
            assert SabotageService.get_tax_rate() == 0.13

        await engine.dispose()

    asyncio.run(run())


def test_npc_prices_change_during_sabotage():
    """Verify NPC prices actually change when resource_multipliers are active.

    get_item_base_price() already embeds crisis multipliers via SabotageService,
    so get_npc_buy_price() and get_npc_sell_price() are automatically crisis-adjusted.
    """
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 25, 17, 0, 0)

            from backend.natbirzha.models.inventory import CANONICAL_ITEMS, get_npc_sell_price
            from backend.natbirzha.services.npc_service import NPCReserveService

            raw_base = float(CANONICAL_ITEMS["fuel_diesel"]["base_price"])
            sell_cap_mult = float(nat_settings.NPC_SELL_CAP_MULT)
            base_sell = round(raw_base * sell_cap_mult, 2)

            # Before sabotage — multiplier is 1.0, prices are base
            quote_before = NPCReserveService.get_npc_quote("fuel_diesel")
            assert quote_before["crisis_multiplier"] == 1.0
            assert quote_before["npc_sell_price"] == base_sell

            # Start fuel_crisis: fuel_diesel +50%
            await SabotageService.start_sabotage(
                session, sabotage_id="fuel_crisis", actor_id=1, now=now
            )
            quote_during = NPCReserveService.get_npc_quote("fuel_diesel")
            assert quote_during["crisis_multiplier"] == 1.50
            # NPC sell price should now be base * 1.5 * NPC_SELL_CAP_MULT
            expected_sell_during = round(raw_base * 1.50 * sell_cap_mult, 2)
            assert quote_during["npc_sell_price"] == expected_sell_during, (
                f"Expected NPC sell {expected_sell_during}, got {quote_during['npc_sell_price']}"
            )

            # energy_crisis: energy +50% — diesel should NOT be affected
            await SabotageService.stop_sabotage(session, actor_id=1, sabotage_id="fuel_crisis", now=now)
            await SabotageService.start_sabotage(
                session, sabotage_id="energy_crisis", actor_id=1, now=now
            )
            quote_energy = NPCReserveService.get_npc_quote("fuel_diesel")
            assert quote_energy["crisis_multiplier"] == 1.0  # diesel not in energy_crisis mults
            assert quote_energy["npc_sell_price"] == base_sell

            await SabotageService.stop_sabotage(session, actor_id=1, sabotage_id="energy_crisis", now=now)

            # After all stopped — back to base
            quote_after = NPCReserveService.get_npc_quote("fuel_diesel")
            assert quote_after["crisis_multiplier"] == 1.0
            assert quote_after["npc_sell_price"] == base_sell

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_sabotages_catalog_completeness()
    test_two_concurrent_sabotages_and_compounded_multipliers()
    test_stock_shock_positive_and_negative()
    test_loss_for_all_crises()
    test_sabotage_tax_rates()
    test_npc_prices_change_during_sabotage()
    print("NATBIRZHA sabotages and crises (multi-active + crisis/boom catalog + tax shocks): PASS")

