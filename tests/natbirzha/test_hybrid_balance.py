"""Hybrid production should retain the combined output of its source plants."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.hybrid_merger_service import HYBRID_RECIPES, HybridMergerService
from backend.natbirzha.services.business_investment import reference_value
from backend.natbirzha.config import nat_settings


def _after_tax_profit(spec: dict, stage: int) -> float:
    profile = spec["stage_rates"][stage]
    revenue = reference_value(spec["outputs_per_hour"]) * profile["output"]
    inputs = reference_value(spec["inputs_per_hour"]) * profile["input"]
    maintenance = spec["base_maintenance_per_hour"] * profile["maintenance"]
    return (revenue - inputs - maintenance) * (1 - nat_settings.TAX_RATE)


def test_level_ten_oil_and_gas_hybrid_is_not_weaker_than_both_source_plants() -> None:
    oil_well = get_business_spec("small_oil_well_v2")
    gas_well = get_business_spec("gas_well_v2")
    hybrid = get_business_spec("hybrid_oilman")

    assert oil_well is not None and gas_well is not None and hybrid is not None
    assert hybrid["max_stage"] == 50
    assert hybrid["outputs_per_hour"]["oil_crude"] > oil_well["outputs_per_hour"]["oil_crude"]
    assert hybrid["outputs_per_hour"]["gas_natural"] > gas_well["outputs_per_hour"]["gas_natural"]
    assert _after_tax_profit(hybrid, 10) >= (
        _after_tax_profit(oil_well, 10) + _after_tax_profit(gas_well, 10)
    )


def test_merging_two_level_ten_oil_plants_starts_hybrid_at_level_ten() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            async with sessions() as session:
                user = User(tg_id=992901, full_name="Oil Hybrid Player")
                session.add(user)
                await session.flush()
                company = NatCompany(
                    user_id=user.id, name="Oil Hybrid Company", specialization="oilman", cash=1_000_000
                )
                session.add(company)
                await session.flush()
                source_ids = []
                for business_type in ("small_oil_well_v2", "gas_well_v2"):
                    spec = get_business_spec(business_type)
                    source = NatBusiness(
                        company_id=company.id,
                        business_type=business_type,
                        specialization="oilman",
                        stage=10,
                        status="ACTIVE",
                        capital_invested=spec["open_cost"],
                        base_maintenance_per_hour=spec["base_maintenance_per_hour"],
                    )
                    session.add(source)
                    await session.flush()
                    source_ids.append(source.id)
                for item_id, quantity in HYBRID_RECIPES["hybrid_oilman"]["resource_requirements"].items():
                    session.add(NatInventory(
                        company_id=company.id,
                        item_id=item_id,
                        quantity=float(quantity) * 10,
                        reserved_quantity=0.0,
                        avg_cost_basis=1.0,
                    ))
                await session.flush()

                result = await HybridMergerService.open_hybrid(
                    session, company.id, "hybrid_oilman", *source_ids
                )
                hybrid = await session.get(NatBusiness, result["hybrid_business_id"])
                assert hybrid.stage == 10
        finally:
            await engine.dispose()

    asyncio.run(check())
