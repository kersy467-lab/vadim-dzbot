"""Every selectable industry must create a playable V2 starter company."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import INDUSTRIES, starter_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.industry_service import IndustryService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_all_industries_bootstrap_with_starter_business_and_supply() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            for index, industry_id in enumerate(INDUSTRIES, start=1):
                company = await CompanyService.create_company(
                    session,
                    90_000 + index,
                    f"Starter {industry_id}",
                    industry_id,
                    ticker=f"S{index:02d}",
                )
                expected = starter_business_spec(industry_id)
                business = await session.scalar(select(NatBusiness).where(NatBusiness.company_id == company.id))
                assert business is not None
                assert business.business_type == expected["id"]
                assert business.specialization == industry_id
                assert business.status == "ACTIVE"

                inventory = list((await session.execute(
                    select(NatInventory).where(NatInventory.company_id == company.id)
                )).scalars().all())
                by_item = {row.item_id: row.quantity for row in inventory}
                for item_id, hourly in expected["inputs_per_hour"].items():
                    # Catalog values such as scaled water demand are
                    # non-terminating decimals; tolerate storage rounding.
                    buffer_hours = 24.0 if item_id in {"beer", "wine", "aged_spirits"} else 4.0
                    assert by_item.get(item_id, 0.0) + 1e-6 >= float(hourly) * buffer_hours

                if index == 1:
                    # Keep the four-hour bootstrap check inside one tax period.
                    # Using wall-clock company creation makes this assertion
                    # time-dependent near the 12:00 / 00:00 production cutoff.
                    settled_at = datetime(2026, 1, 1, 12, 0)
                    business.last_settled_at = settled_at
                    first_shift = await IdleEconomyService.settle_company(
                        session, company.id, now=settled_at + timedelta(hours=4)
                    )
                    assert first_shift["xp_gained"] == 80
                    assert first_shift["progression"]["level"] == 1
                    assert first_shift["progression"]["xp_to_next"] == 70

            total = await session.scalar(select(func.count(NatBusiness.id)))
            assert total == len(INDUSTRIES)
            overview = await IndustryService.overview(session)
            assert overview["total_companies"] == len(INDUSTRIES)
            assert {item["id"] for item in overview["items"]} == set(INDUSTRIES)
            assert all(item["company_count"] == 1 for item in overview["items"])

        await engine.dispose()

    asyncio.run(check())
