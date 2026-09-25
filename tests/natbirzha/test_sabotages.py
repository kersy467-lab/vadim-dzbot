"""Comprehensive tests for Natbirzha economic sabotages and crisis events."""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock
from backend.natbirzha.models.inventory import get_item_base_price, get_npc_buy_price
from backend.natbirzha.catalogs.sabotages import SABOTAGES_CATALOG, get_sabotage_spec
from backend.natbirzha.services.sabotage_service import SabotageService
from backend.natbirzha.services.state_credit_service import StateCreditService


def test_sabotages_catalog_completeness():
    """Verify that all 12 required crisis events are fully defined in the catalog."""
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
    ]
    assert len(SABOTAGES_CATALOG) == 12
    for sab_id in required_ids:
        assert sab_id in SABOTAGES_CATALOG
        spec = get_sabotage_spec(sab_id)
        assert spec is not None
        assert spec["name"]
        assert spec["icon"]
        assert spec["description"]
        assert spec["duration_hours"] in (12, 24, 48)


def test_sabotage_lifecycle_and_single_active_constraint():
    """Test start, active query, single active constraint, and stop."""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 25, 10, 0, 0)
            
            # Initially no active sabotage
            active = await SabotageService.get_active_sabotage(session, now=now)
            assert active is None
            assert SabotageService.get_income_multiplier("agrarian") == 1.0
            assert SabotageService.get_resource_multiplier_sync("energy") == 1.0

            # Start fuel_crisis (24h)
            start_res = await SabotageService.start_sabotage(
                session, sabotage_id="fuel_crisis", actor_id=123456789012, now=now
            )
            assert start_res["success"] is True
            assert start_res["sabotage_id"] == "fuel_crisis"

            # Check active sabotage
            active = await SabotageService.get_active_sabotage(session, now=now)
            assert active is not None
            assert active.sabotage_id == "fuel_crisis"
            assert active.is_active is True

            # In-memory multipliers during fuel_crisis:
            # oilman +30%, logistics -25%, agrarian -10%, construction -10%
            assert SabotageService.get_income_multiplier("oilman") == 1.30
            assert SabotageService.get_income_multiplier("logistics") == 0.75
            assert SabotageService.get_income_multiplier("agrarian") == 0.90
            assert SabotageService.get_income_multiplier("construction") == 0.90
            assert SabotageService.get_income_multiplier("builder") == 0.90  # alias
            assert SabotageService.get_income_multiplier("miner") == 1.0

            # Resource price: fuel_diesel +50%
            base_diesel = get_item_base_price("fuel_diesel")
            assert base_diesel == round(1.2 * 1.50, 2)
            # Unaffected resource
            assert get_item_base_price("grain") == 20.0

            # Attempting to start another sabotage while fuel_crisis is active must fail
            try:
                await SabotageService.start_sabotage(
                    session, sabotage_id="water_shortage", actor_id=123456789012, now=now
                )
            except ValueError as exc:
                assert "Уже активен саботаж" in str(exc)
            else:
                raise AssertionError("Should not allow starting a second sabotage simultaneously")

            # Stop early
            stop_res = await SabotageService.stop_sabotage(
                session, actor_id=123456789012, reason="TEST_STOP", now=now
            )
            assert stop_res["success"] is True
            assert stop_res["sabotage_id"] == "fuel_crisis"

            # Verify multipliers are reset
            assert SabotageService.get_income_multiplier("oilman") == 1.0
            assert SabotageService.get_income_multiplier("logistics") == 1.0
            assert get_item_base_price("fuel_diesel") == 1.2
            assert await SabotageService.get_active_sabotage(session, now=now) is None

        await engine.dispose()

    asyncio.run(run())


def test_stock_shock_and_default_mechanics():
    """Test stock price shock, dividend freeze, and credit freeze during state_default."""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            # Create listed company and stock
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
            
            # Start state_default (-30% stock shock)
            res = await SabotageService.start_sabotage(
                session, sabotage_id="state_default", actor_id=7755842535, now=now
            )
            assert res["success"] is True
            assert res["affected_stocks"] == 1

            # Verify stock price was shocked from 100 to 70 (-30%)
            await session.refresh(stock)
            assert stock.current_price == 70.0
            assert stock.last_valuation == 700_000.0

            # Verify default flags
            assert SabotageService.are_dividends_blocked() is True
            assert SabotageService.are_new_credits_blocked() is True
            assert SabotageService.get_bond_price_multiplier() == 0.65

            # Attempting state credit request during default must fail
            try:
                await StateCreditService.request(
                    session, company, principal=5_000, term_days=3, now=now
                )
            except ValueError as exc:
                assert "приостановлена" in str(exc).lower() or "дефолт" in str(exc).lower()
            else:
                raise AssertionError("New credits must be blocked during state default")

            # Check expiration when time passes > 12h
            future_now = now + timedelta(hours=13)
            expired = await SabotageService.check_and_expire(session, now=future_now)
            assert expired is not None
            assert expired["expired"] is True
            assert expired["sabotage_id"] == "state_default"

            # Multipliers and blocks are lifted
            assert SabotageService.are_dividends_blocked() is False
            assert SabotageService.are_new_credits_blocked() is False
            assert SabotageService.get_bond_price_multiplier() == 1.0

        await engine.dispose()

    asyncio.run(run())


def test_key_rate_credit_and_bond_impact():
    """Test key_rate crisis raising credit rate by +10% and discounting bonds by 10%."""
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = datetime(2026, 9, 25, 14, 0, 0)
            await SabotageService.start_sabotage(
                session, sabotage_id="key_rate", actor_id=1, now=now
            )
            assert SabotageService.get_credit_rate_delta() == 0.10
            assert SabotageService.get_bond_price_multiplier() == 0.90

            await SabotageService.stop_sabotage(session, actor_id=1, now=now)
            assert SabotageService.get_credit_rate_delta() == 0.0
            assert SabotageService.get_bond_price_multiplier() == 1.0

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_sabotages_catalog_completeness()
    test_sabotage_lifecycle_and_single_active_constraint()
    test_stock_shock_and_default_mechanics()
    test_key_rate_credit_and_bond_impact()
    print("NATBIRZHA sabotages and crises: PASS")
