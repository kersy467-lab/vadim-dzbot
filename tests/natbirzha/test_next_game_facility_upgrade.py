import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameInventory, NatNextGameLedger,
)
from backend.natbirzha.services.next_game_service import NextGameService


def test_facility_upgrade_requires_company_level_and_improves_output_without_more_inputs():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        started = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 810101, "Сетевая корпорация")
            await NextGameService.select_sector(session, 810101, "energy")
            await NextGameService.select_branch(session, 810101, "renewables")
            await NextGameService.build_facility(session, 810101, now=started)
            company = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 810101
            ))
            facility = await session.scalar(select(NatNextGameFacility).where(
                NatNextGameFacility.company_id == company.id
            ))

            with pytest.raises(ValueError, match="уровень компании"):
                await NextGameService.upgrade_facility(session, 810101, "renewables")
            assert facility.level == 1

            company.level = 2
            upgraded = await NextGameService.upgrade_facility(session, 810101, "renewables")
            assert upgraded["facility"]["level"] == 2
            assert upgraded["upgrade_cost"] == 2_500
            assert upgraded["output_multiplier"] == 1.25

            result = await NextGameService.settle_company(
                session, 810101, now=started + timedelta(minutes=5)
            )
            assert result["cycles_completed"] == 1
            energy = await session.scalar(select(NatNextGameInventory).where(
                NatNextGameInventory.company_id == company.id,
                NatNextGameInventory.item_id == "energy",
            ))
            assert energy.quantity == pytest.approx(11.25)
            ledger = list((await session.scalars(select(NatNextGameLedger).where(
                NatNextGameLedger.company_id == company.id
            ))).all())
            upgrade = next(row for row in ledger if row.action == "FACILITY_UPGRADE")
            operation = next(row for row in ledger if row.action == "OPERATING_COST")
            assert upgrade.cash_company_delta == -2_500
            assert upgrade.cash_treasury_delta == 2_500
            assert operation.cash_company_delta == -25

            facility.level = 10
            company.level = 60
            with pytest.raises(ValueError, match="максимального уровня"):
                await NextGameService.upgrade_facility(session, 810101, "renewables")

        await engine.dispose()

    asyncio.run(check())
