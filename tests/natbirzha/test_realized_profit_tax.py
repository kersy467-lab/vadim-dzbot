"""Tax only cash business results and resource inventory that has been sold."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, get_item_base_price
from backend.natbirzha.models.market import NatMarketTrade
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.services.tax_service import TaxService
from backend.natbirzha.tax_rules import get_period_bounds


def test_unsold_resource_output_is_not_taxable_and_costs_are_capitalized() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now().replace(minute=0, second=0, microsecond=0)
        period_start, period_end = get_period_bounds(now)
        async with sessions() as session:
            company = NatCompany(
                user_id=940_001, name="Inventory Corp", specialization="power_engineer", cash=50_000,
            )
            session.add(company)
            await session.flush()
            spec = get_business_spec("diesel_power_station")
            assert spec is not None
            business = NatBusiness(
                company_id=company.id,
                business_type="diesel_power_station",
                specialization="power_engineer",
                stage=1,
                status="ACTIVE",
                capital_invested=float(spec["open_cost"]),
                base_income_per_hour=0.0,
                base_maintenance_per_hour=float(spec["base_maintenance_per_hour"]),
                last_settled_at=period_start,
                metadata_json={"sale_mode": "HOLD"},
            )
            session.add_all([
                business,
                NatInventory(company_id=company.id, item_id="fuel_diesel", quantity=100.0, avg_cost_basis=1.2),
                NatInventory(company_id=company.id, item_id="water", quantity=1_000.0, avg_cost_basis=2.0),
            ])
            await session.flush()
            fuel_before = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id, NatInventory.item_id == "fuel_diesel"
            ))
            fuel_quantity_before = float(fuel_before.quantity)
            water_before = await session.scalar(
                select(NatInventory).where(
                    NatInventory.company_id == company.id, NatInventory.item_id == "water"
                )
            )
            water_quantity_before = float(water_before.quantity)

            settled = await IdleEconomyService.settle_company(
                session, company.id, now=period_start + timedelta(hours=1)
            )
            output = await session.scalar(
                select(NatInventory).where(
                    NatInventory.company_id == company.id, NatInventory.item_id == "energy"
                )
            )
            fuel_after = await session.scalar(
                select(NatInventory).where(
                    NatInventory.company_id == company.id, NatInventory.item_id == "fuel_diesel"
                )
            )
            water_after = await session.scalar(
                select(NatInventory).where(
                    NatInventory.company_id == company.id, NatInventory.item_id == "water"
                )
            )
            assert output is not None and output.quantity > 0
            consumed_cost = (
                (fuel_quantity_before - fuel_after.quantity) * 1.2
                + (water_quantity_before - water_after.quantity) * 2.0
            )
            capitalized_cost = consumed_cost + settled["maintenance_cash"]
            assert output.avg_cost_basis == pytest.approx(capitalized_cost / output.quantity, abs=1e-5)
            assert output.avg_cost_basis < get_item_base_price("energy")

            # The inventory's reference value appears in legacy analytics, but
            # it is neither realized revenue nor a current-period tax base.
            tax = await TaxService.summary(session, company.id, now=period_end)
            assert tax["principal_due"] == 0.0
            assert tax["current_period_realized_profit"] == 0.0
            assert tax["current_period_estimated_tax"] == 0.0
            assert settled["gross_value"] > 0.0

        await engine.dispose()

    asyncio.run(check())


def test_player_market_sale_records_revenue_fee_and_inventory_cogs() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now().replace(minute=0, second=0, microsecond=0)
        async with sessions() as session:
            seller = NatCompany(user_id=940_004, name="Market Seller", specialization="miner", cash=1_000)
            buyer = NatCompany(user_id=940_005, name="Market Buyer", specialization="miner", cash=1_000)
            session.add_all([seller, buyer])
            await session.flush()
            session.add(NatInventory(
                company_id=seller.id, item_id="energy", quantity=10.0,
                reserved_quantity=0.0, avg_cost_basis=4.0,
            ))
            await session.flush()

            await MarketService.create_order(session, seller, "SELL", "energy", 10.0, 10.0, commit=False)
            await MarketService.create_order(session, buyer, "BUY", "energy", 10.0, 10.0, commit=False)
            trade = await session.scalar(select(NatMarketTrade))
            assert trade is not None
            tax = await TaxService.summary(session, seller.id, now=now)
            expected_profit = trade.total_amount - trade.quantity * 4.0 - trade.fee_amount
            assert tax["current_period_realized_profit"] == pytest.approx(expected_profit)

        await engine.dispose()

    asyncio.run(check())


def test_cash_business_profit_is_taxed_when_income_and_maintenance_settle(monkeypatch) -> None:
    from backend.natbirzha.services import idle_company_settlement

    original_spec = get_business_spec

    def visible_legacy_spec(business_type: str):
        spec = original_spec(business_type)
        if business_type == "retail_chain" and spec is not None:
            return {**spec, "legacy_hidden": False}
        return spec

    monkeypatch.setattr(idle_company_settlement, "get_business_spec", visible_legacy_spec)

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now().replace(minute=0, second=0, microsecond=0)
        period_start, _ = get_period_bounds(now)
        async with sessions() as session:
            company = NatCompany(
                user_id=940_006, name="Cash Business Corp", specialization="retail", cash=50_000,
            )
            session.add(company)
            await session.flush()
            spec = get_business_spec("retail_chain")
            assert spec is not None and spec["mechanic"] == "cash_income"
            session.add(NatBusiness(
                company_id=company.id,
                business_type="retail_chain",
                specialization="retail",
                stage=1,
                status="ACTIVE",
                capital_invested=float(spec["open_cost"]),
                base_income_per_hour=float(spec["base_income_per_hour"]),
                base_maintenance_per_hour=float(spec["base_maintenance_per_hour"]),
                last_settled_at=period_start,
            ))
            await session.flush()

            settled = await IdleEconomyService.settle_company(
                session, company.id, now=period_start + timedelta(hours=1)
            )
            tax = await TaxService.summary(session, company.id, now=period_start + timedelta(hours=1))
            expected_profit = settled["gross_cash"] - settled["maintenance_cash"]
            assert expected_profit > 0
            assert tax["current_period_realized_profit"] == pytest.approx(expected_profit, abs=1e-5)
            assert tax["current_period_estimated_tax"] == pytest.approx(expected_profit * 0.13, abs=1e-2)

        await engine.dispose()

    asyncio.run(check())


def test_partial_and_full_npc_sales_tax_positive_net_realized_profit_only() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = get_game_now().replace(minute=0, second=0, microsecond=0)
        period_start, period_end = get_period_bounds(now)
        async with sessions() as session:
            company = NatCompany(
                user_id=940_002, name="Realized Corp", specialization="power_engineer", cash=50_000,
            )
            loss_company = NatCompany(
                user_id=940_003, name="Loss Corp", specialization="power_engineer", cash=50_000,
            )
            session.add_all([company, loss_company])
            await session.flush()
            session.add_all([
                NatInventory(company_id=company.id, item_id="energy", quantity=100.0, avg_cost_basis=4.0),
                NatInventory(company_id=loss_company.id, item_id="energy", quantity=10.0, avg_cost_basis=20.0),
            ])
            await session.flush()

            first = await NPCReserveService.execute_npc_trade(session, company, "energy", "SELL", 25.0)
            assert first["success"] is True
            inv = await session.scalar(
                select(NatInventory).where(
                    NatInventory.company_id == company.id, NatInventory.item_id == "energy"
                )
            )
            assert inv.quantity == 75.0
            partial = await TaxService.summary(session, company.id, now=now)
            assert partial["current_period_realized_profit"] == 100.0
            assert partial["current_period_estimated_tax"] == 13.0

            second = await NPCReserveService.execute_npc_trade(session, company, "energy", "SELL", 75.0)
            assert second["success"] is True
            inv = await session.scalar(
                select(NatInventory).where(
                    NatInventory.company_id == company.id, NatInventory.item_id == "energy"
                )
            )
            assert inv.quantity == 0.0
            closed = await TaxService.summary(session, company.id, now=period_end)
            assert closed["principal_due"] == 52.0
            assert closed["liabilities"][-1]["taxable_profit"] == 400.0

            # A sale below inventory cost creates a company-period loss and
            # must not create a negative or zero-rate tax liability.
            losing_sale = await NPCReserveService.execute_npc_trade(
                session, loss_company, "energy", "SELL", 10.0
            )
            assert losing_sale["success"] is True
            loss_current = await TaxService.summary(session, loss_company.id, now=now)
            assert loss_current["current_period_realized_profit"] == -120.0
            loss_tax = await TaxService.summary(session, loss_company.id, now=period_end)
            assert loss_tax["principal_due"] == 0.0
            assert loss_tax["liabilities"] == []

        await engine.dispose()

    asyncio.run(check())
