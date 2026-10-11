import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameInventory, NatNextGameLedger,
)
from backend.natbirzha.models.next_game_managers import NatNextGameManager
from backend.natbirzha.next_game_catalog import get_next_game_catalog
from backend.natbirzha.next_game_map import build_progression_map
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_manager_service import (
    assign_manager, ensure_manager_awards, manager_discount,
)
from backend.natbirzha.services.next_game_service.common import (
    facility_output_multiplier, facility_upgrade_cost, facility_upgrade_duration,
)
from backend.natbirzha.api.next_game_progression_routes import rebirth_disabled
from backend.natbirzha.next_game_continuous_migration import migrate_next_game_continuous_progression


def test_each_industry_maps_its_existing_facilities_to_nine_territories():
    catalog = get_next_game_catalog()
    for sector in catalog:
        view = build_progression_map(
            sector["id"], catalog, branch_path=[], facility_levels={}, company_level=1,
        )
        assert len(view["territories"]) == 9
        mapped_ids = {
            branch["id"]
            for territory in view["territories"]
            for branch in territory["facilities"]
        }
        source_ids = {branch["id"] for branch in sector["branches"]}
        assert mapped_ids == source_ids
        assert view["revealed"] is False


def test_upgrade_curve_and_legacy_rebirth_endpoint_is_disabled():
    assert facility_upgrade_cost(1) == 150
    assert facility_upgrade_cost(49) == 7_350
    assert facility_upgrade_duration(1) == 3
    assert facility_upgrade_duration(49) == 147
    assert facility_output_multiplier(50) == pytest.approx(2.96)
    assert facility_output_multiplier(51) == pytest.approx(3.0)

    async def check_disabled_route():
        with pytest.raises(HTTPException) as error:
            await rebirth_disabled()
        assert error.value.status_code == 410

    asyncio.run(check_disabled_route())


def test_continuous_progression_migration_is_repeatable_and_preserves_existing_rows():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                "CREATE TABLE nat_next_game_companies "
                "(id INTEGER PRIMARY KEY, level INTEGER NOT NULL, xp INTEGER NOT NULL)"
            )
            await connection.exec_driver_sql(
                "CREATE TABLE nat_next_game_facilities "
                "(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, branch_id VARCHAR(64) NOT NULL, "
                "level INTEGER NOT NULL, next_cycle_at TIMESTAMP NOT NULL)"
            )
            await connection.exec_driver_sql(
                "INSERT INTO nat_next_game_companies VALUES (1, 67, 66000)"
            )
            await connection.exec_driver_sql(
                "INSERT INTO nat_next_game_facilities VALUES (1, 1, 'renewables', 54, '2026-10-11 12:00:00')"
            )
            await migrate_next_game_continuous_progression(connection)
            await migrate_next_game_continuous_progression(connection)
            company = (await connection.exec_driver_sql(
                "SELECT level, xp FROM nat_next_game_companies WHERE id=1"
            )).first()
            facility = (await connection.exec_driver_sql(
                "SELECT level, upgrade_target_level, upgrade_finishes_at, upgrade_reserved_cash "
                "FROM nat_next_game_facilities WHERE id=1"
            )).first()
            columns = (await connection.exec_driver_sql(
                "PRAGMA table_info('nat_next_game_managers')"
            )).fetchall()
            assert tuple(company) == (67, 66000)
            assert tuple(facility) == (54, None, None, 0)
            assert columns
        await engine.dispose()

    asyncio.run(check())


def test_map_reveals_at_eighth_level_and_restores_existing_route_state():
    catalog = get_next_game_catalog()
    sector = next(row for row in catalog if row["id"] == "resources")
    start = next(row for row in sector["branches"] if row["is_starting_branch"])
    path = [start["id"], "ferrous"]

    hidden = build_progression_map(
        "resources", catalog, branch_path=path,
        facility_levels={start["id"]: 7, "ferrous": 2}, company_level=8,
    )
    shown = build_progression_map(
        "resources", catalog, branch_path=path,
        facility_levels={start["id"]: 8, "ferrous": 2}, company_level=8,
    )

    assert hidden["revealed"] is False
    assert shown["revealed"] is True
    assert shown["current_branch_id"] == "ferrous"
    mapped = {branch["id"]: branch for region in shown["sectors"]
              for area in region["territories"] for branch in area["facilities"]}
    assert mapped[start["id"]]["state"] == "built"
    assert mapped["ferrous"]["state"] == "built"


def test_map_only_marks_real_successors_as_available():
    catalog = get_next_game_catalog()
    sector = next(row for row in catalog if row["id"] == "energy")
    start = next(row for row in sector["branches"] if row["id"] == "renewables")
    path = ["renewables"]
    view = build_progression_map(
        "energy", catalog, branch_path=path,
        facility_levels={}, company_level=8, consumed_branch_ids={"renewables"},
    )
    mapped = {branch["id"]: branch for region in view["sectors"]
              for area in region["territories"] for branch in area["facilities"]}

    assert set(start["next_branch_ids"]).issubset(mapped)
    assert mapped["renewables"]["state"] == "merged"
    assert all(mapped[branch_id]["state"] == "available" for branch_id in start["next_branch_ids"])
    assert all(branch["state"] == "locked" for branch_id, branch in mapped.items()
               if branch_id not in {"renewables", *start["next_branch_ids"]})


def test_company_snapshot_includes_the_persistent_industry_map():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 10, 11, 12)
        async with sessions() as session:
            await NextGameService.create_company(session, 661401, "Карта прогресса")
            await NextGameService.select_sector(session, 661401, "energy")
            await NextGameService.select_branch(session, 661401, "renewables")
            await NextGameService.build_facility(session, 661401, now=now)
            facility = await session.scalar(select(NatNextGameFacility))
            facility.level = 8
            snapshot = await NextGameService.snapshot(session, 661401, now=now)
            assert snapshot["progression_map"]["revealed"] is True
            assert len(snapshot["progression_map"]["territories"]) == 9
            assert snapshot["progression_map"]["current_branch_id"] == "renewables"
        await engine.dispose()

    asyncio.run(check())


def test_factory_upgrade_reserves_cost_then_completes_once_after_server_timer():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime.now().replace(microsecond=0) + timedelta(days=1)
        async with sessions() as session:
            await NextGameService.create_company(session, 661402, "Промышленная карта")
            await NextGameService.select_sector(session, 661402, "energy")
            await NextGameService.select_branch(session, 661402, "renewables")
            await NextGameService.build_facility(session, 661402, now=start)
            company = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 661402,
            ))
            company.level = 2
            facility = await session.scalar(select(NatNextGameFacility))
            balance_before = float(company.cash)

            result = await NextGameService.upgrade_facility(
                session, 661402, "renewables", now=start,
            )
            assert result["upgrade_cost"] == 150
            assert result["duration_seconds"] == 3
            assert facility.level == 1
            assert facility.upgrade_target_level == 2
            assert facility.upgrade_finishes_at == start + timedelta(seconds=3)
            assert facility.upgrade_reserved_cash == 150
            assert company.cash == balance_before - 150

            with pytest.raises(ValueError):
                await NextGameService.upgrade_facility(session, 661402, "renewables", now=start)

            pending = await NextGameService.snapshot(session, 661402, now=start + timedelta(seconds=2))
            assert pending["facilities"][0]["level"] == 1
            assert pending["facilities"][0]["upgrade_target_level"] == 2

            completed = await NextGameService.snapshot(session, 661402, now=start + timedelta(seconds=4))
            assert completed["facilities"][0]["level"] == 2
            assert completed["facilities"][0]["upgrade_target_level"] is None
            assert completed["company"]["xp"] == 600
            repeated = await NextGameService.snapshot(session, 661402, now=start + timedelta(seconds=5))
            assert repeated["company"]["xp"] == 600

        await engine.dispose()

    asyncio.run(check())


def test_manager_milestones_are_guaranteed_and_move_between_owned_factories():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime.now().replace(microsecond=0)
        async with sessions() as session:
            await NextGameService.create_company(session, 661403, "Команда производства")
            await NextGameService.select_sector(session, 661403, "energy")
            await NextGameService.select_branch(session, 661403, "renewables")
            await NextGameService.build_facility(session, 661403, now=start)
            company = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 661403,
            ))
            company.level = 45
            company.branch_path = ["renewables", "thermal"]
            second = NatNextGameFacility(
                company_id=company.id, branch_id="thermal", level=1,
                next_cycle_at=start + timedelta(minutes=5),
            )
            session.add(second)
            managers = await ensure_manager_awards(session, company)
            assert [(row.reward_level, row.rarity, row.discount_pct) for row in managers] == [
                (5, "common", 2), (15, "rare", 4), (30, "epic", 6), (45, "legendary", 8),
            ]
            assert len(await ensure_manager_awards(session, company)) == 4
            first_facility = await session.scalar(select(NatNextGameFacility).where(
                NatNextGameFacility.branch_id == "renewables",
            ))
            manager = managers[0]
            await assign_manager(session, 661403, manager.id, "renewables")
            assert manager.facility_id == first_facility.id
            assert await manager_discount(session, first_facility.id) == pytest.approx(.02)

            moved = await assign_manager(session, 661403, manager.id, "thermal")
            assert moved["manager"]["branch_id"] == "thermal"
            assert manager.facility_id == second.id
            assert await manager_discount(session, first_facility.id) == 0
            assert await manager_discount(session, second.id) == pytest.approx(.02)
            with pytest.raises(ValueError):
                await assign_manager(session, 661403, manager.id, "not-owned")

            snapshot = await NextGameService.snapshot(session, 661403, now=start)
            assert len(snapshot["managers"]) == 4
            assert next(row for row in snapshot["managers"] if row["id"] == manager.id)["branch_id"] == "thermal"
        await engine.dispose()

    asyncio.run(check())


def test_company_levels_continue_after_sixty_and_manager_only_reduces_cash_cost():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime.now().replace(microsecond=0)
        async with sessions() as session:
            await NextGameService.create_company(session, 661404, "Длинная прогрессия")
            await NextGameService.select_sector(session, 661404, "energy")
            await NextGameService.select_branch(session, 661404, "renewables")
            await NextGameService.build_facility(session, 661404, now=start)
            company = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 661404,
            ))
            facility = await session.scalar(select(NatNextGameFacility))
            company.level, company.xp = 60, 59_900
            managers = await ensure_manager_awards(session, company)
            await assign_manager(session, 661404, managers[0].id, "renewables")
            await NextGameService.settle_company(session, 661404, now=start + timedelta(minutes=5))
            assert company.xp == 60_100
            assert company.level == 61
            output = await session.scalar(select(NatNextGameInventory.quantity).where(
                NatNextGameInventory.company_id == company.id,
                NatNextGameInventory.item_id == "energy",
            ))
            ledger = list((await session.scalars(select(NatNextGameLedger).where(
                NatNextGameLedger.company_id == company.id,
                NatNextGameLedger.action == "OPERATING_COST",
            ))).all())
            assert output == pytest.approx(9)
            assert ledger[-1].cash_company_delta == pytest.approx(-24.5)
            assert facility.level == 1
        await engine.dispose()

    asyncio.run(check())
