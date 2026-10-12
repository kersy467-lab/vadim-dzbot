"""PVC cases and collectible manager employees for NATBIRZHA 2.0."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameLedger
from backend.natbirzha.models.next_game_managers import NatNextGameManager
from backend.natbirzha.models.next_game_community import NatNextGameProfile
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_community_service import profile
from backend.natbirzha.services.next_game_manager_service import (
    MANAGER_REWARDS, apply_manager_discount, assign_manager, ensure_manager_awards,
    manager_discount,
)
from backend.natbirzha.services.next_game_employee_service import (
    CASE_PRICE_PVC, CASE_DROP_ODDS, NextGameEmployeeService,
)
from backend.natbirzha.api.next_game_mutation import mutate
from backend.natbirzha.next_game_employees_migration import migrate_next_game_employees
from backend.natbirzha.api import build_natbirzha_router
from backend.natbirzha.services.next_game_service.common import _utcnow


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return engine, sessions


def test_case_catalog_discloses_price_rarity_level_ranges_and_cash_discounts():
    assert CASE_PRICE_PVC == 25
    assert sum(row["probability"] for row in CASE_DROP_ODDS) == pytest.approx(1)
    assert [(row["rarity"], row["probability"], row["level_min"], row["level_max"], row["discount_pct"])
            for row in CASE_DROP_ODDS] == [
        ("common", .70, 1, 10, 2),
        ("rare", .22, 11, 20, 4),
        ("epic", .07, 21, 30, 6),
        ("legendary", .01, 31, 50, 8),
    ]


def test_case_open_debits_profile_and_writes_employee_and_pvc_ledger_atomically(monkeypatch):
    async def check():
        import backend.natbirzha.services.next_game_employee_service as employee_service

        engine, sessions = await _database()
        try:
            async with sessions() as session:
                await NextGameService.create_company(session, 991101, "Case buyer")
                company = await NextGameService._owned_company(session, 991101)
                wallet = await profile(session, company.id)
                wallet.pvc_balance = 100
                await session.commit()

                monkeypatch.setattr(employee_service, "_draw_case_employee", lambda: {
                    "rarity": "legendary", "level": 42, "name": "Avery Quinn",
                })
                actor = SimpleNamespace(id=991101)
                payload = {}

                async def open_case():
                    return await NextGameEmployeeService.open_case(session, 991101)

                first = await mutate(
                    session, actor, "employee-case-1", "/next-game/employees/cases/open",
                    payload, open_case,
                )
                replay = await mutate(
                    session, actor, "employee-case-1", "/next-game/employees/cases/open",
                    payload, open_case,
                )

                assert first == replay
                assert first["employee"]["source"] == "case"
                assert first["employee"]["name"] == "Avery Quinn"
                assert first["employee"]["level"] == 42
                assert first["employee"]["rarity"] == "legendary"
                assert first["employee"]["discount_pct"] == 8
                await session.refresh(wallet)
                assert wallet.pvc_balance == 75
                assert await session.scalar(select(func.count(NatNextGameManager.id)).where(
                    NatNextGameManager.company_id == company.id,
                    NatNextGameManager.source == "case",
                )) == 1
                ledger = await session.scalar(select(NatNextGameLedger).where(
                    NatNextGameLedger.company_id == company.id,
                    NatNextGameLedger.action == "EMPLOYEE_CASE_OPEN",
                ))
                assert ledger.metadata_json["pvc_delta"] == -25
                assert ledger.metadata_json["employee_id"] == first["employee"]["id"]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_case_open_rejects_insufficient_pvc_without_partial_employee_or_ledger(monkeypatch):
    async def check():
        import backend.natbirzha.services.next_game_employee_service as employee_service

        engine, sessions = await _database()
        try:
            async with sessions() as session:
                await NextGameService.create_company(session, 991102, "No case cash")
                company = await NextGameService._owned_company(session, 991102)
                company_id = company.id
                wallet = await profile(session, company.id)
                wallet.pvc_balance = 24
                await session.commit()
                monkeypatch.setattr(employee_service, "_draw_case_employee", lambda: {
                    "rarity": "common", "level": 4, "name": "Casey Brooks",
                })
                with pytest.raises(ValueError, match="25 PVC"):
                    await NextGameEmployeeService.open_case(session, 991102)
                await session.rollback()
                assert await session.scalar(select(func.count(NatNextGameManager.id)).where(
                    NatNextGameManager.company_id == company_id,
                )) == 0
                assert await session.scalar(select(func.count(NatNextGameLedger.id)).where(
                    NatNextGameLedger.company_id == company_id,
                    NatNextGameLedger.action == "EMPLOYEE_CASE_OPEN",
                )) == 0
                await session.refresh(wallet)
                assert wallet.pvc_balance == 24
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_case_employee_assigns_to_factory_affects_cycle_cash_only_and_cannot_be_deleted(monkeypatch):
    async def check():
        import backend.natbirzha.services.next_game_employee_service as employee_service

        engine, sessions = await _database()
        try:
            async with sessions() as session:
                await NextGameService.create_company(session, 991103, "Hiring company")
                company = await NextGameService._owned_company(session, 991103)
                company.level = 45
                wallet = await profile(session, company.id)
                wallet.pvc_balance = 100
                from backend.natbirzha.models.next_game import NatNextGameFacility
                facility = NatNextGameFacility(
                    company_id=company.id, branch_id="renewables", level=1,
                    next_cycle_at=_utcnow() + timedelta(days=1),
                )
                session.add(facility)
                await session.flush()
                monkeypatch.setattr(employee_service, "_draw_case_employee", lambda: {
                    "rarity": "epic", "level": 28, "name": "Riley Morgan",
                })
                employee = await NextGameEmployeeService.open_case(session, 991103)
                employee_id = employee["employee"]["id"]
                await assign_manager(session, 991103, employee_id, "renewables")

                discount = await manager_discount(session, facility.id)
                recipe = {"operating_cost": 100, "cycle_seconds": 3600,
                          "economics": {"npc_profit": 20}}
                discounted = apply_manager_discount(recipe, discount)
                assert discount == pytest.approx(.06)
                assert discounted["operating_cost"] == pytest.approx(94)
                assert discounted["economics"]["npc_profit"] == pytest.approx(26)

                with pytest.raises(ValueError, match="назначенного"):
                    await NextGameEmployeeService.delete_employee(session, 991103, employee_id)
                await session.refresh(company)
                assigned = await session.get(NatNextGameManager, employee_id)
                assert assigned.facility_id == facility.id
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_case_employee_can_be_deleted_when_unassigned_but_milestone_staff_are_protected(monkeypatch):
    async def check():
        import backend.natbirzha.services.next_game_employee_service as employee_service

        engine, sessions = await _database()
        try:
            async with sessions() as session:
                await NextGameService.create_company(session, 991104, "Staff company")
                company = await NextGameService._owned_company(session, 991104)
                company.level = 45
                wallet = await profile(session, company.id)
                wallet.pvc_balance = 100
                from backend.natbirzha.models.next_game import NatNextGameFacility
                facility = NatNextGameFacility(
                    company_id=company.id, branch_id="renewables", level=1,
                    next_cycle_at=_utcnow() + timedelta(days=1),
                )
                session.add(facility)
                await session.flush()
                old_award = NatNextGameManager(
                    company_id=company.id, reward_level=5, name="Анна Белова",
                    rarity="common", discount_pct=2, source="milestone", level=5,
                    facility_id=facility.id,
                )
                session.add(old_award)
                await session.flush()
                monkeypatch.setattr(employee_service, "_draw_case_employee", lambda: {
                    "rarity": "rare", "level": 18, "name": "Jordan Hayes",
                })
                opened = await NextGameEmployeeService.open_case(session, 991104)
                await NextGameEmployeeService.delete_employee(
                    session, 991104, opened["employee"]["id"],
                )
                assert await session.get(NatNextGameManager, opened["employee"]["id"]) is None

                milestone_rows = await ensure_manager_awards(session, company)
                assert len([row for row in milestone_rows if row.source == "milestone"]) == 4
                assert [(row.name, row.rarity, row.discount_pct) for row in milestone_rows
                        if row.source == "milestone"] == [
                    (name, rarity, discount)
                    for _level, name, rarity, discount in MANAGER_REWARDS
                ]
                guaranteed = next(row for row in milestone_rows if row.source == "milestone")
                normalized = next(row for row in milestone_rows if row.reward_level == 5)
                assert normalized.id == old_award.id
                assert normalized.name == "Amelia Brooks"
                assert normalized.facility_id == facility.id
                assert normalized.discount_pct == 2
                with pytest.raises(ValueError) as error:
                    await NextGameEmployeeService.delete_employee(session, 991104, guaranteed.id)
                assert "Гарантированных" in str(error.value)
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_employee_api_routes_are_registered_under_the_next_game_prefix():
    paths = {route.path for route in build_natbirzha_router(admin_only=False).routes}
    assert "/natbirzha/next-game/employees" in paths
    assert "/natbirzha/next-game/employees/cases/open" in paths
    assert "/natbirzha/next-game/employees/{employee_id}" in paths


def test_employee_case_migration_backfills_milestone_level_and_is_repeatable():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(
                    "CREATE TABLE nat_next_game_managers ("
                    "id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, reward_level INTEGER NOT NULL, "
                    "name VARCHAR(80) NOT NULL, rarity VARCHAR(16) NOT NULL, discount_pct INTEGER NOT NULL, "
                    "facility_id INTEGER, awarded_at TIMESTAMP NOT NULL, "
                    "CONSTRAINT uq_next_manager_reward UNIQUE(company_id, reward_level))"
                )
                await connection.exec_driver_sql(
                    "INSERT INTO nat_next_game_managers "
                    "(id, company_id, reward_level, name, rarity, discount_pct, awarded_at) "
                    "VALUES (1, 7, 15, 'Old name', 'rare', 4, '2026-10-12 00:00:00')"
                )
                await migrate_next_game_employees(connection)
                await migrate_next_game_employees(connection)
                columns = (await connection.exec_driver_sql(
                    "PRAGMA table_info('nat_next_game_managers')"
                )).all()
                row = (await connection.exec_driver_sql(
                    "SELECT reward_level, level, source, name FROM nat_next_game_managers WHERE id=1"
                )).one()
                assert {column[1] for column in columns} >= {"level", "source"}
                assert tuple(row) == (15, 15, "milestone", "Old name")
        finally:
            await engine.dispose()

    asyncio.run(check())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
