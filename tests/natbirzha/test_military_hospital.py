"""Hospital admission, recovery, treatment and repair lifecycle checks."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.military_infrastructure import NatMilitaryInfrastructure
from backend.natbirzha.models.hospital import NatHospitalWard
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.hospital_service import HospitalService
from backend.natbirzha.services.military_infrastructure_service import (
    FACILITY_MAX_LEVELS, MilitaryInfrastructureService,
)


NOW = datetime(2026, 9, 27, 12, 0, 0)


async def _company(session, user_id: int, name: str, units: dict[str, int]):
    company = NatCompany(
        user_id=user_id, name=name, specialization="agrarian", cash=100_000.0,
    )
    session.add(company)
    await session.flush()
    session.add(NatMilitaryInfrastructure(
        company_id=company.id, hospital_level=1, repair_depot_level=1,
    ))
    for unit_type, quantity in units.items():
        session.add(NatArmyUnit(
            company_id=company.id, unit_type=unit_type, quantity=quantity,
            level=1, readiness=10_000, experience=0,
        ))
    return company


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    from fastapi import FastAPI
    from backend.natbirzha.api import build_natbirzha_router
    from backend.natbirzha.services.world_reset_service import WorldResetService

    app = FastAPI()
    app.include_router(build_natbirzha_router())
    routes = set(app.openapi()["paths"].keys())
    assert {
        "/natbirzha/military/hospital/status",
        "/natbirzha/military/hospital/treat",
        "/natbirzha/military/hospital/treat-all",
        "/natbirzha/military/hospital/collect",
    }.issubset(routes)
    assert "nat_hospital_wards" in {
        table.name for table in WorldResetService.resettable_tables()
    }

    assert HospitalService.classify_losses(
        {"infantry": 100, "tanks": 10}, mode="PVE"
    ) == {
        "light_wounded": {"infantry": 70, "tanks": 7},
        "severe_wounded": {"infantry": 30, "tanks": 3},
        "fatalities": {"infantry": 0, "tanks": 0},
    }
    assert HospitalService.classify_losses(
        {"infantry": 100}, mode="PVP"
    ) == {
        "light_wounded": {"infantry": 55},
        "severe_wounded": {"infantry": 38},
        "fatalities": {"infantry": 7},
    }
    assert FACILITY_MAX_LEVELS["hospital"] == 20
    assert FACILITY_MAX_LEVELS["repair_depot"] == 20
    quote = MilitaryInfrastructureService.upgrade_quote(
        NatMilitaryInfrastructure(company_id=1, hospital_level=19, repair_depot_level=19),
        "hospital",
    )
    assert quote["target_level"] == 20 and quote["max_level"] == 20
    try:
        MilitaryInfrastructureService.upgrade_quote(
            NatMilitaryInfrastructure(company_id=1, hospital_level=20, repair_depot_level=20),
            "repair_depot",
        )
    except ValueError as exc:
        assert "максимальный" in str(exc)
    else:
        raise AssertionError("Hospital and repair levels must cap at 20")

    async with sessions() as session:
        company = await _company(
            session, 970001, "Hospital PvE", {"infantry": 300, "tanks": 20}
        )
        pve = await HospitalService.apply_combat_losses(
            session, company.id, {"infantry": 100, "tanks": 10}, mode="PVE", now=NOW
        )
        assert pve["light_wounded"] == {"infantry": 70, "tanks": 7}
        assert pve["hospitalized"] == {"infantry": 30, "tanks": 3}
        assert pve["fatalities"] == {}
        army = await HospitalService.army_counts(session, company.id)
        assert army["infantry"] == 270 and army["tanks"] == 17

        company = await _company(
            session, 970002, "Hospital Overflow", {"infantry": 2_000}
        )
        overflow = await HospitalService.apply_combat_losses(
            session, company.id, {"infantry": 2_000}, mode="PVE", now=NOW
        )
        assert overflow["hospitalized"] == {"infantry": 500}
        assert overflow["fatalities"] == {"infantry": 100}
        assert (await HospitalService.army_counts(session, company.id))["infantry"] == 1_400

        repair_overflow_company = await _company(
            session, 970006, "Repair Overflow", {"tanks": 300}
        )
        repair_overflow = await HospitalService.apply_combat_losses(
            session, repair_overflow_company.id, {"tanks": 300}, mode="PVE", now=NOW
        )
        assert repair_overflow["hospitalized"] == {"tanks": 50}
        assert repair_overflow["fatalities"] == {"tanks": 40}
        assert (await HospitalService.army_counts(session, repair_overflow_company.id))["tanks"] == 210

        company = await _company(
            session, 970003, "Hospital PvP", {"infantry": 500}
        )
        pvp = await HospitalService.apply_combat_losses(
            session, company.id, {"infantry": 100}, mode="PVP", now=NOW
        )
        assert pvp["hospitalized"] == {"infantry": 38}
        assert pvp["fatalities"] == {"infantry": 7}
        assert (await HospitalService.army_counts(session, company.id))["infantry"] == 455

        status = await HospitalService.get_status(session, company.id, now=NOW)
        assert status["hospital"]["capacity"] == 500
        assert status["repair_depot"]["capacity"] == 50

        # Treatment reserves beds, charges once, and returns units only when collected.
        started = await HospitalService.start_treatment(
            session, company.id, "infantry", 30, now=NOW
        )
        assert started["cash_paid"] == 300
        assert started["duration_minutes"] == 1
        assert await HospitalService.collect_treated(session, company.id, now=NOW) == {}
        collected = await HospitalService.collect_treated(
            session, company.id, now=NOW + timedelta(minutes=1)
        )
        assert collected == {"infantry": 30}
        assert (await HospitalService.army_counts(session, company.id))["infantry"] == 485

        # A failed repair never charges cash or consumes only part of its materials.
        company = await _company(session, 970004, "Repair Depot", {"tanks": 10})
        await ArmyService.apply_losses(session, company.id, {"tanks": 2})
        ward = NatHospitalWard(
            company_id=company.id, unit_type="tanks", wounded_count=2, healing_count=0,
        )
        session.add(ward)
        session.add(NatInventory(
            company_id=company.id, item_id="steel", quantity=0.5, reserved_quantity=0.0,
        ))
        cash_before = company.cash
        try:
            await HospitalService.start_treatment(
                session, company.id, "tanks", 2, now=NOW
            )
        except ValueError as exc:
            assert "0.5" in str(exc)
        else:
            raise AssertionError("A repair without enough steel must be rejected")
        assert company.cash == cash_before
        assert ward.wounded_count == 2

        inventory = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == company.id, NatInventory.item_id == "steel",
        ))
        inventory.quantity = 2.0
        instant = await HospitalService.start_treatment(
            session, company.id, "tanks", 2, instant=True, now=NOW
        )
        assert instant["cash_paid"] == 600
        assert instant["materials_paid"] == {"steel": 1.0}
        assert (await HospitalService.army_counts(session, company.id))["tanks"] == 10

        all_company = await _company(
            session, 970005, "Treat All", {"infantry": 100, "drones": 20}
        )
        session.add_all([
            NatHospitalWard(company_id=all_company.id, unit_type="infantry", wounded_count=100),
            NatHospitalWard(company_id=all_company.id, unit_type="drones", wounded_count=20),
            NatInventory(
                company_id=all_company.id, item_id="electronics", quantity=4.0,
                reserved_quantity=0.0,
            ),
        ])
        await session.flush()
        all_result = await HospitalService.start_all_treatments(
            session, all_company.id, now=NOW
        )
        assert set(all_result["started"]) == {"infantry", "drones"}
        all_status = await HospitalService.get_status(session, all_company.id, now=NOW)
        assert all_status["hospital"]["occupied"] == 100
        assert all_status["repair_depot"]["occupied"] == 20

        persistent = await _company(session, 970007, "Restart Queue", {"infantry": 100})
        await HospitalService.apply_combat_losses(
            session, persistent.id, {"infantry": 50}, mode="PVE", now=NOW
        )
        await HospitalService.start_treatment(
            session, persistent.id, "infantry", 10, now=NOW
        )
        await session.commit()

        # A fresh session (same persisted database, like a restarted process) retains the timer.
        async with sessions() as restarted:
            restored = await HospitalService.get_status(
                restarted, persistent.id, now=NOW + timedelta(seconds=30)
            )
            ward = restored["hospital"]["wards"][0]
            assert ward["healing_count"] == 10 and ward["ready"] is False
            collected = await HospitalService.collect_treated(
                restarted, persistent.id, now=NOW + timedelta(minutes=1)
            )
            assert collected == {"infantry": 10}
            assert (await HospitalService.army_counts(restarted, persistent.id))["infantry"] == 95

    await engine.dispose()

    # Existing installations get the two new columns with level-one defaults.
    from backend.natbirzha.migrations import _migrate_v19_hospital_repair

    migration_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with migration_engine.begin() as connection:
        await connection.execute(text("""
            CREATE TABLE nat_military_infrastructure (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL UNIQUE,
                command_center_level INTEGER NOT NULL DEFAULT 0
            )
        """))
        await connection.execute(text(
            "INSERT INTO nat_military_infrastructure (company_id) VALUES (42)"
        ))
        await _migrate_v19_hospital_repair(connection)
        row = (await connection.execute(text(
            "SELECT hospital_level, repair_depot_level "
            "FROM nat_military_infrastructure WHERE company_id=42"
        ))).one()
        assert row == (1, 1)
    await migration_engine.dispose()
    print("NATBIRZHA hospital and repair lifecycle checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
