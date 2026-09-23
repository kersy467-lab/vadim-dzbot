"""Industry PVC bonuses stay relevant to the company's own business sector."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.company_constants import VALID_SPECIALIZATIONS
from backend.natbirzha.services.industry_upgrade_service import IndustryUpgradeService


def test_every_company_industry_has_a_pvc_upgrade_and_logistics_needs_no_lithium() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            catalog = IndustryUpgradeService.catalog()
            assert {item["specialization"] for item in catalog} == set(VALID_SPECIALIZATIONS)

            company = NatCompany(
                user_id=990011,
                name="Logistics Premium",
                specialization="logistics",
                pvc_balance=1_000,
            )
            session.add(company)
            await session.flush()

            first = await IndustryUpgradeService.purchase_next_level(
                session, company.id, "industry-logistics-1"
            )
            assert first["level"] == 1
            assert first["pvc_balance"] < 1_000
            assert IndustryUpgradeService.bonus_multiplier(company, "logistics") == 1.05
            assert IndustryUpgradeService.bonus_multiplier(company, "miner") == 1.0

            await IndustryUpgradeService.purchase_next_level(
                session, company.id, "industry-logistics-2"
            )
            assert IndustryUpgradeService.bonus_multiplier(company, "logistics") == 1.10

        await engine.dispose()

    asyncio.run(check())


def test_industry_bonus_scales_business_output_rates() -> None:
    from backend.natbirzha.catalogs.businesses import get_business_spec
    from backend.natbirzha.models.business import NatBusiness
    from backend.natbirzha.services.business_rates import cash_business_rates, resource_business_rates

    cash_spec = get_business_spec("logistics_company")
    cash_business = NatBusiness(
        business_type=cash_spec["id"], stage=1, efficiency=1.0, health=100,
        base_income_per_hour=100, base_maintenance_per_hour=0,
    )
    baseline_cash = cash_business_rates(cash_business, cash_spec, upgrading=False)
    bonus_cash = cash_business_rates(
        cash_business, cash_spec, upgrading=False, output_bonus_multiplier=1.05
    )
    assert bonus_cash.gross_per_hour == round(baseline_cash.gross_per_hour * 1.05, 4)

    resource_spec = next(
        item for item in __import__(
            "backend.natbirzha.catalogs.businesses", fromlist=["visible_business_specs"]
        ).visible_business_specs(specialization="logistics")
        if item["mechanic"] == "resource_production"
    )
    resource_business = NatBusiness(
        business_type=resource_spec["id"], stage=1, efficiency=1.0, health=100,
        base_maintenance_per_hour=0,
    )
    baseline_resource = resource_business_rates(resource_business, resource_spec, upgrading=False)
    bonus_resource = resource_business_rates(
        resource_business, resource_spec, upgrading=False, output_bonus_multiplier=1.05
    )
    assert bonus_resource.output_multiplier == round(baseline_resource.output_multiplier * 1.05, 6)
    assert bonus_resource.input_multiplier == baseline_resource.input_multiplier


def test_logistics_upgrade_increases_logistics_output_without_increasing_input_use() -> None:
    from datetime import datetime

    from sqlalchemy import select

    from backend.natbirzha.catalogs.businesses import get_business_spec
    from backend.natbirzha.models.business import NatBusiness
    from backend.natbirzha.models.inventory import NatInventory
    from backend.natbirzha.services.business_rates import resource_business_rates
    from backend.natbirzha.services.idle_economy_service import IdleEconomyService

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            now = datetime(2026, 9, 24, 12)
            company = NatCompany(
                user_id=990012,
                name="Logistics Output",
                specialization="logistics",
                industry_upgrade_levels_json={"logistics": 1},
            )
            session.add(company)
            await session.flush()
            spec = get_business_spec("courier_service_v2")
            business = NatBusiness(
                company_id=company.id,
                business_type=spec["id"],
                specialization="logistics",
                stage=1,
                status="ACTIVE",
                base_income_per_hour=0,
                base_maintenance_per_hour=8,
                last_settled_at=now,
                health=100,
                efficiency=1,
                metadata_json={"sale_mode": "HOLD"},
            )
            session.add(business)
            session.add(NatInventory(
                company_id=company.id,
                item_id="fuel_diesel",
                quantity=20,
                reserved_quantity=0,
                avg_cost_basis=0,
            ))
            await session.flush()

            _, _, worked, _, _ = await IdleEconomyService._settle_resource_segment(
                session,
                company.id,
                business,
                spec,
                hours=1,
                upgrading=False,
                industry_bonus_multiplier=IndustryUpgradeService.bonus_multiplier(company, "logistics"),
            )
            boosted_rate = resource_business_rates(
                business,
                spec,
                upgrading=False,
                output_bonus_multiplier=IndustryUpgradeService.bonus_multiplier(company, "logistics"),
            ).output_multiplier
            inputs = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id,
                NatInventory.item_id == "fuel_diesel",
            ))
            output = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id,
                NatInventory.item_id == "logistics_capacity",
            ))
            assert worked == 1
            assert inputs.quantity == 18
            assert output.quantity == round(
                float(spec["outputs_per_hour"]["logistics_capacity"]) * boosted_rate, 6
            )
        await engine.dispose()

    asyncio.run(check())
