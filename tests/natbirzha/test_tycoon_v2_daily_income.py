"""Idle settlements feed a durable daily-profit source for IPO and dividends."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily
from backend.natbirzha.models.inventory import NatInventory, get_item_base_price
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_idle_settlements_accumulate_business_daily_profit() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_401, name="Daily Ledger", specialization="miner", cash=30_000)
            session.add(company)
            await session.flush()
            session.add_all([
                NatInventory(company_id=company.id, item_id="energy", quantity=264, avg_cost_basis=10),
                NatInventory(company_id=company.id, item_id="water", quantity=200, avg_cost_basis=2),
                NatInventory(company_id=company.id, item_id="fuel_diesel", quantity=6, avg_cost_basis=1.2),
                NatInventory(company_id=company.id, item_id="food", quantity=3, avg_cost_basis=45),
            ])
            await session.commit()
            opened = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
            first = await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=1))
            assert first["tax"]["principal_due"] == 0.0
            assert first["tax_blocked"] is False
            await IdleEconomyService.settle_company(session, company.id, now=now + timedelta(hours=3))

            row = await session.scalar(select(NatBusinessIncomeDaily).where(
                NatBusinessIncomeDaily.business_id == opened["business"]["id"]
            ))
            business = await session.get(NatBusiness, opened["business"]["id"])
            spec = get_business_spec(business.business_type)
            rates = resource_business_rates(business, spec, upgrading=False)
            expected_gross = sum(
                float(quantity) * rates.output_multiplier * get_item_base_price(item_id) * 3
                for item_id, quantity in spec["outputs_per_hour"].items()
            )
            expected_resource_cost = sum(
                float(quantity) * rates.input_multiplier * get_item_base_price(item_id) * 3
                for item_id, quantity in spec["inputs_per_hour"].items()
            )
            assert row.gross_income == round(expected_gross, 2)
            assert row.maintenance == round(rates.maintenance_per_hour * 3, 2)
            assert row.resource_cost == round(expected_resource_cost, 2)
            assert row.net_profit == round(
                expected_gross - rates.maintenance_per_hour * 3 - expected_resource_cost, 2
            )

        await engine.dispose()

    asyncio.run(check())


def test_v8_migration_reconciles_resource_gross_profit() -> None:
    async def check() -> None:
        from backend.natbirzha.migrations import _migrate_v8_reconcile_resource_gross_profit
        from backend.natbirzha.models.business import NatBusiness

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=9_402, name="Reconcile Corp", specialization="miner", cash=30_000)
            session.add(company)
            await session.flush()
            biz = NatBusiness(
                company_id=company.id,
                business_type="coal_open_pit",
                specialization="miner",
                stage=1,
                status="ACTIVE",
                capital_invested=12_000,
                base_income_per_hour=0.0,
                base_maintenance_per_hour=8.4,
                health=100.0,
                efficiency=1.0,
                metadata_json={"sale_mode": "HOLD"},
                last_settled_at=now,
            )
            session.add(biz)
            await session.flush()
            # Simulate a stale un-reconciled negative profit entry from before the fix:
            broken_entry = NatBusinessIncomeDaily(
                business_id=biz.id,
                date=now.date(),
                gross_income=0.0,
                maintenance=25.2,
                salary=0.0,
                resource_cost=0.0,
                net_profit=-25.2,
            )
            session.add(broken_entry)
            await session.commit()

        # Run migration on connection
        async with engine.begin() as conn:
            await _migrate_v8_reconcile_resource_gross_profit(conn)

        async with sessions() as session:
            healed = await session.scalar(select(NatBusinessIncomeDaily).where(
                NatBusinessIncomeDaily.business_id == biz.id
            ))
            assert healed is not None
            spec = get_business_spec(biz.business_type)
            rates = resource_business_rates(biz, spec, upgrading=False)
            worked_hours = healed.maintenance / rates.maintenance_per_hour
            expected_gross = sum(
                float(quantity) * rates.output_multiplier * get_item_base_price(item_id) * worked_hours
                for item_id, quantity in spec["outputs_per_hour"].items()
            )
            assert healed.gross_income == round(expected_gross, 2)
            assert healed.maintenance == 25.2
            assert healed.net_profit == round(expected_gross - 25.2, 2)

        await engine.dispose()

    asyncio.run(check())
