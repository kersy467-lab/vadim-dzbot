"""The dynamic V2 inventory capacity must protect the offline production window."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_high_output_company_can_settle_an_offline_segment_past_old_storage_cap():
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        start = datetime(2026, 9, 20, 12, 0)
        end = start + timedelta(hours=11)
        async with sessions() as session:
            company = NatCompany(
                user_id=941_001,
                name="Offline Water Corp",
                specialization="water",
                level=60,
                cash=10_000_000,
            )
            session.add(company)
            await session.flush()
            spec = get_business_spec("regional_water_operator")
            assert spec is not None
            business = NatBusiness(
                company_id=company.id,
                business_type=spec["id"],
                specialization=company.specialization,
                stage=50,
                status="ACTIVE",
                health=100,
                efficiency=1,
                capital_invested=spec["open_cost"],
                base_income_per_hour=0,
                base_maintenance_per_hour=spec["base_maintenance_per_hour"],
                last_settled_at=start,
                metadata_json={"sale_mode": "HOLD"},
            )
            session.add(business)
            rates = resource_business_rates(business, spec, upgrading=False)
            session.add_all([
                NatInventory(
                    company_id=company.id,
                    item_id=item_id,
                    quantity=max(10_000_000.0, float(per_hour) * rates.input_multiplier * 12 + 1),
                    avg_cost_basis=1.0,
                )
                for item_id, per_hour in spec["inputs_per_hour"].items()
            ])
            await session.flush()

            result = await IdleEconomyService.settle_company(session, company.id, now=end)
            output = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id,
                NatInventory.item_id == "water",
            ))
            assert result["settled_hours"] == 11
            assert output is not None
            assert output.quantity > 1_000_000
            assert business.status != "PAUSED_STORAGE"

        await engine.dispose()

    asyncio.run(check())
