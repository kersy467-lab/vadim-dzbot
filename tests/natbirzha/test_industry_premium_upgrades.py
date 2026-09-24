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


def test_industry_upgrade_refreshes_stale_company_before_purchase() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            company = NatCompany(
                user_id=990016,
                name="Concurrent Premium Buyer",
                specialization="logistics",
                pvc_balance=1_000,
            )
            session.add(company)
            await session.commit()
            company_id = company.id

        async with sessions() as stale_session:
            stale_company = await stale_session.get(NatCompany, company_id)
            assert stale_company is not None and stale_company.pvc_balance == 1_000
            await stale_session.commit()

            async with sessions() as fresh_session:
                first = await IndustryUpgradeService.purchase_next_level(
                    fresh_session, company_id, "industry-logistics-concurrent-first"
                )
                await fresh_session.commit()
                assert first["level"] == 1

            second = await IndustryUpgradeService.purchase_next_level(
                stale_session, company_id, "industry-logistics-concurrent-second"
            )
            await stale_session.commit()
            persisted = await stale_session.get(NatCompany, company_id)
            assert second["level"] == 2
            assert persisted.industry_upgrade_levels_json["logistics"] == 2
            assert persisted.pvc_balance == 760
        await engine.dispose()

    asyncio.run(check())


def test_industry_upgrade_track_reaches_200_percent_with_bounded_prices() -> None:
    catalog = next(
        item for item in IndustryUpgradeService.catalog()
        if item["specialization"] == "logistics"
    )
    assert catalog["max_level"] == 40
    assert catalog["bonus_per_level_pct"] == 5
    assert catalog["max_bonus_pct"] == 200
    assert catalog["level_costs"][:3] == [80, 160, 320]
    assert catalog["level_costs"][3:] == [320] * 37


def test_industry_upgrade_preserves_legacy_levels_and_caps_at_200_percent() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            company = NatCompany(
                user_id=990013,
                name="Legacy Premium Levels",
                specialization="logistics",
                pvc_balance=20_000,
                industry_upgrade_levels_json={"logistics": 3, "miner": 2},
            )
            session.add(company)
            await session.flush()
            assert IndustryUpgradeService.bonus_multiplier(company, "logistics") == 1.15

            for level in range(4, 41):
                await IndustryUpgradeService.purchase_next_level(
                    session, company.id, f"industry-logistics-{level}"
                )

            quote = IndustryUpgradeService.quote(company)
            assert quote["level"] == 40
            assert quote["bonus_pct"] == 200
            assert quote["max_bonus_pct"] == 200
            assert quote["next_level_cost"] is None
            assert IndustryUpgradeService.bonus_multiplier(company, "logistics") == 3.0
            assert company.industry_upgrade_levels_json["miner"] == 2
            try:
                await IndustryUpgradeService.purchase_next_level(
                    session, company.id, "industry-logistics-over-cap"
                )
            except ValueError as exc:
                assert "максим" in str(exc).lower()
            else:
                raise AssertionError("Industry production upgrade must stop at level 40")
        await engine.dispose()

    asyncio.run(check())


def test_factory_cycle_uses_completion_time_industry_bonus_without_more_inputs() -> None:
    from datetime import timedelta

    from sqlalchemy import select

    from backend.natbirzha.config import get_game_now
    from backend.natbirzha.models.company import NatFactory
    from backend.natbirzha.models.inventory import NatInventory
    from backend.natbirzha.services.production_service import ProductionTickEngine

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            company = NatCompany(
                user_id=990014,
                name="Factory PVC Output",
                specialization="metallurgist",
                level=8,
                industry_upgrade_levels_json={"metallurgist": 40},
            )
            session.add(company)
            await session.flush()
            factory = NatFactory(
                company_id=company.id,
                building_type="rolling_mill",
                specialization="metallurgist",
                level=1,
                workers=30,
                technology_level=0,
                is_active=True,
            )
            steel = NatInventory(
                company_id=company.id, item_id="steel", quantity=10,
                reserved_quantity=0, avg_cost_basis=0,
            )
            energy = NatInventory(
                company_id=company.id, item_id="energy", quantity=88,
                reserved_quantity=0, avg_cost_basis=0,
            )
            session.add_all((factory, steel, energy))
            await session.flush()

            now = get_game_now()
            started = await ProductionTickEngine.start_cycle(
                session, company, factory, now=now
            )
            assert started["success"] is True
            assert steel.quantity == 8
            assert energy.quantity == 44
            factory = await session.scalar(
                select(NatFactory).where(NatFactory.id == factory.id)
            )
            completed = await ProductionTickEngine.complete_cycle(
                session, company, factory,
                now=now + timedelta(seconds=started["duration_seconds"] + 1),
            )
            assert completed["success"] is True
            assert completed["outputs_produced"]["rolled_metal"] == 6.0

            # A cycle already running when an upgrade is bought uses the
            # multiplier active at completion; its inputs were already charged.
            company.industry_upgrade_levels_json = {}
            next_cycle_start = now + timedelta(seconds=started["duration_seconds"] + 1)
            second_started = await ProductionTickEngine.start_cycle(
                session, company, factory, now=next_cycle_start
            )
            assert second_started["success"] is True
            assert steel.quantity == 6
            assert energy.quantity == 0
            company.industry_upgrade_levels_json = {"metallurgist": 1}
            factory = await session.scalar(
                select(NatFactory).where(NatFactory.id == factory.id)
            )
            second_completed = await ProductionTickEngine.complete_cycle(
                session, company, factory,
                now=next_cycle_start + timedelta(seconds=second_started["duration_seconds"] + 1),
            )
            assert second_completed["success"] is True
            assert second_completed["outputs_produced"]["rolled_metal"] == 2.1

            company.industry_upgrade_levels_json = {"metallurgist": 40}
            assert ProductionTickEngine.output_multiplier(factory, company) == 3.0
            assert ProductionTickEngine.output_multiplier(factory) == 1.0
        await engine.dispose()

    asyncio.run(check())


def test_pvc_industry_purchase_settles_old_v2_production_before_upgrading() -> None:
    from datetime import timedelta
    from math import isclose

    from backend.natbirzha.api.premium_routes import purchase_industry_upgrade
    from backend.natbirzha.config import get_game_now, normalize_dt
    from backend.natbirzha.models.business import NatBusiness
    from backend.natbirzha.models.company import NatFactory
    from backend.natbirzha.models.inventory import NatInventory
    from backend.natbirzha.catalogs.businesses import get_business_spec
    from backend.natbirzha.services.business_rates import resource_business_rates
    from backend.natbirzha.services import production_automation
    from sqlalchemy import select

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            now = get_game_now()
            company = NatCompany(
                user_id=990015,
                name="Settle Before Premium",
                specialization="power_engineer",
                level=6,
                pvc_balance=500,
                cash=10_000,
            )
            session.add(company)
            await session.flush()
            business = NatBusiness(
                company_id=company.id,
                business_type="wind_park_v2",
                specialization="power_engineer",
                status="ACTIVE",
                stage=1,
                efficiency=1.0,
                health=100,
                base_income_per_hour=0,
                base_maintenance_per_hour=0,
                last_settled_at=now - timedelta(hours=1),
                metadata_json={"sale_mode": "HOLD"},
            )
            factory_start = now - timedelta(minutes=10)
            factory = NatFactory(
                company_id=company.id,
                building_type="solar_plant",
                specialization="power_engineer",
                level=1,
                workers=10,
                automation_level=1,
                automation_enabled=True,
                automation_status="RUNNING",
                current_recipe="generate_solar",
                cycle_started_at=factory_start,
                cycle_ready_at=factory_start + timedelta(seconds=54),
            )
            grid = NatInventory(
                company_id=company.id,
                item_id="grid_quota",
                quantity=20,
                reserved_quantity=0,
                avg_cost_basis=0,
            )
            session.add_all((business, factory, grid))
            await session.flush()

            catch_up_limit = production_automation.MAX_AUTOMATION_CATCH_UP_CYCLES
            production_automation.MAX_AUTOMATION_CATCH_UP_CYCLES = 2
            try:
                await purchase_industry_upgrade(
                    idempotency_key="settle-before-industry-purchase",
                    company=company,
                    session=session,
                )
            finally:
                production_automation.MAX_AUTOMATION_CATCH_UP_CYCLES = catch_up_limit

            business = await session.get(NatBusiness, business.id)
            settled_hours = (
                normalize_dt(business.last_settled_at)
                - normalize_dt(now - timedelta(hours=1))
            ).total_seconds() / 3600
            assert settled_hours > 0
            spec = get_business_spec("wind_park_v2")
            baseline = resource_business_rates(business, spec, upgrading=False)
            expected_old_output = (
                spec["outputs_per_hour"]["energy"]
                * baseline.output_multiplier
                * settled_hours
            )
            energy = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id,
                NatInventory.item_id == "energy",
            ))
            assert energy is not None and energy.quantity > 0
            factory_output = energy.quantity - expected_old_output
            completed_cycles = round(factory_output / 15.0)
            assert completed_cycles > 0
            assert isclose(factory_output, completed_cycles * 15.0, rel_tol=1e-6), (
                "factory cycles elapsed before the upgrade must use the old 1.0x output multiplier"
            )
            assert company.industry_upgrade_levels_json["power_engineer"] == 1
            assert isclose(energy.quantity, expected_old_output + completed_cycles * 15.0, rel_tol=1e-5)
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
