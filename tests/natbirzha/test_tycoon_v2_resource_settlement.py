"""Resource businesses must consume inputs continuously and pause honestly."""

import asyncio
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, get_item_base_price
from backend.natbirzha.api.business_routes import SaleModeRequest
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomePeriod
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_sale_mode_api_rejects_npc_and_keeps_hold() -> None:
    assert SaleModeRequest(mode="HOLD").mode == "HOLD"
    with pytest.raises(ValidationError):
        SaleModeRequest(mode="NPC")


def test_resource_business_consumes_inputs_and_pauses_when_supply_ends() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_101, name="Energy Corp", specialization="power_engineer", cash=40_000)
            session.add_all([
                company,
                NatInventory(company_id=1, item_id="fuel_diesel", quantity=10, avg_cost_basis=1.2),
                NatInventory(company_id=1, item_id="water", quantity=2, avg_cost_basis=2),
            ])
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "diesel_power_station", now=now)
            business = await session.get(NatBusiness, opened["business"]["id"])
            assert business.metadata_json["sale_mode"] == "HOLD"
            with pytest.raises(ValueError, match="HOLD"):
                await BusinessService.configure_sale_mode(
                    session, company.id, opened["business"]["id"], "NPC"
                )
            # Simulate an old database row with the former NPC sale preference.
            business.metadata_json = {**business.metadata_json, "sale_mode": "NPC"}
            cash_before_settlement = company.cash

            settled = await IdleEconomyService.settle_company(
                session, company.id, now=now + timedelta(hours=4)
            )
            fuel = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "fuel_diesel"))
            water = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "water"))
            energy = await session.scalar(select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id == "energy"))
            income_period = await session.scalar(select(NatBusinessIncomePeriod).where(
                NatBusinessIncomePeriod.business_id == opened["business"]["id"]
            ))
            business = await session.get(NatBusiness, opened["business"]["id"])

            assert settled["maintenance_cash"] > 0
            assert settled["gross_cash"] == 0.0
            assert company.cash == cash_before_settlement - settled["maintenance_cash"]
            assert 0.0 < fuel.quantity < 10.0
            assert water.quantity == 0.0
            assert energy.quantity > 0.0
            # Unsold output carries input cost plus maintenance into its basis;
            # its reference value remains analytics-only until a sale.
            production_cost = (10.0 - fuel.quantity) * 1.2 + 2.0 * 2.0 + settled["maintenance_cash"]
            assert energy.avg_cost_basis == pytest.approx(production_cost / energy.quantity, abs=1e-5)
            assert income_period is not None
            assert round(income_period.gross_income, 2) == round(
                energy.quantity * get_item_base_price("energy"), 2
            )
            assert business.status == "PAUSED_SUPPLY"

        await engine.dispose()

    asyncio.run(check())
