"""Server-side business opening and upgrade contracts for NATBIRZHA 2.0."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.empire_summary_service import EmpireSummaryService


def test_business_open_and_upgrade_are_server_priced_and_timed() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=8_101, name="Tycoon Corp", specialization="miner", cash=50_000)
            session.add(company)
            await session.commit()

            opened = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
            assert opened["open_cost"] == 12_000.0
            assert opened["remaining_cash"] == 38_000.0
            assert opened["business"]["stage"] == 1
            assert opened["slots"] == {"used": 1, "max": 10, "free": 9}

            upgrade = await BusinessService.start_upgrade(session, company.id, opened["business"]["id"], now=now)
            assert upgrade["cost"] == 600.0
            assert upgrade["target_stage"] == 2
            assert upgrade["ready_at"] == now + timedelta(minutes=3)
            assert upgrade["remaining_cash"] == 37_400.0

            with pytest.raises(ValueError, match="уже выполняется"):
                await BusinessService.start_upgrade(session, company.id, opened["business"]["id"], now=now)

        await engine.dispose()

    asyncio.run(check())


def test_business_slots_scale_by_company_level_and_territory() -> None:
    assert BusinessService.business_slot_limits(level=1, territory_tiles=4, used=1) == {"used": 1, "max": 10, "free": 9}
    assert BusinessService.business_slot_limits(level=30, territory_tiles=20, used=6) == {"used": 6, "max": 39, "free": 33}
    assert BusinessService.business_slot_limits(level=60, territory_tiles=20, used=49) == {"used": 49, "max": 50, "free": 1}


def test_career_businesses_can_repeat_but_explicit_unique_entries_cannot() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(user_id=8_102, name="Repeatable Corp", specialization="miner", cash=100_000)
            session.add(company)
            await session.commit()
            first = await BusinessService.open_business(session, company.id, "coal_open_pit")
            second = await BusinessService.open_business(session, company.id, "coal_open_pit")
            assert first["business"]["id"] != second["business"]["id"]
            assert second["slots"] == {"used": 2, "max": 10, "free": 8}
            summary = await EmpireSummaryService.build(session, company.id)
            assert summary["businesses"][0]["sale_refund"] == 4_800.0

            unique_spec = {**get_business_spec("coal_open_pit"), "unique": True}
            existing = {"coal_open_pit": [NatBusiness(stage=1)]}
            with pytest.raises(ValueError, match="уже принадлежит"):
                BusinessService._validate_open_requirements(company, unique_spec, existing)

            sold = await BusinessService.sell(session, company.id, first["business"]["id"])
            assert sold["refund"] == 4_800.0
        await engine.dispose()

    asyncio.run(check())


def test_prerequisites_use_highest_stage_across_repeated_instances() -> None:
    company = NatCompany(user_id=8_103, name="Prerequisite Corp", specialization="miner", cash=100_000)
    company.level = 4
    company.territory_tiles = 2
    existing = {
        "coal_open_pit": [NatBusiness(stage=2), NatBusiness(stage=8)],
    }
    BusinessService._validate_open_requirements(
        company, get_business_spec("iron_quarry"), existing
    )
