"""Normalized recruitment, snapshots, losses, and compatibility checks."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.military import NatArmy
from backend.natbirzha.services.army_service import ArmyService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        company = NatCompany(
            user_id=920001,
            name="Army Test",
            specialization="metallurgist",
            cash=100_000.0,
        )
        session.add(company)
        await session.flush()
        company_id = company.id
        session.add(NatArmy(company_id=company.id))
        for item_id in ("steel", "electronics", "aluminum", "jet_fuel", "military_gear"):
            session.add(NatInventory(company_id=company.id, item_id=item_id, quantity=100.0))
        await session.commit()

        starting_cash = company.cash
        for unit_type in (
            "infantry",
            "border_guards",
            "tanks",
            "drones",
            "aircraft",
            "air_defense",
        ):
            result = await ArmyService.recruit(session, company, unit_type, 2)
            assert result["unit_type"] == unit_type
            assert result["count_recruited"] == 2
        await session.commit()
        assert company.cash < starting_cash

        snapshot = await ArmyService.snapshot(session, company_id)
        assert snapshot.units == {
            "infantry": 2,
            "border_guards": 2,
            "tanks": 2,
            "drones": 2,
            "aircraft": 2,
            "air_defense": 2,
        }
        assert all(value == 1 for value in snapshot.levels.values())
        assert all(value == 1.0 for value in snapshot.readiness.values())

        await ArmyService.apply_losses(
            session,
            company_id,
            {unit_type: 1 for unit_type in snapshot.units},
        )
        await session.commit()
        after_losses = await ArmyService.snapshot(session, company_id)
        assert all(value == 1 for value in after_losses.units.values())

        try:
            await ArmyService.apply_losses(session, company_id, {"aircraft": 2})
        except ValueError as exc:
            assert "aircraft" in str(exc)
        else:
            raise AssertionError("Losses larger than the locked army must fail")
        await session.rollback()

        status = await ArmyService.compatibility_status(session, company_id)
        for unit_type in (
            "infantry", "border_guards", "tanks", "drones", "aircraft", "air_defense"
        ):
            assert status[unit_type] == 1
        assert status["army_strength"] > 0
        assert set(status["phase_strengths"]) == {"recon", "air", "air_defense", "ground"}

        legacy = await session.scalar(select(NatArmy).where(NatArmy.company_id == company_id))
        assert legacy is not None
        assert legacy.infantry == 1 and legacy.tanks == 1
        assert legacy.army_strength == status["army_strength"]
        rows = (
            await session.execute(
                select(NatArmyUnit).where(NatArmyUnit.company_id == company_id)
            )
        ).scalars().all()
        assert len(rows) == 6

    await engine.dispose()
    print("NATBIRZHA normalized army service checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())

