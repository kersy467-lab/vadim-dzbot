"""Creator custom reward controls and restart-safe scheduler checks."""

import asyncio
from datetime import timedelta

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api.creator_routes import LaunchTournamentRequest
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.models.military import NatTournament
from backend.natbirzha.models.premium import NatPremiumLedgerEntry
from backend.natbirzha.services.creator_service import CreatorService
from backend.natbirzha.services.tournament_service import TournamentService


async def run_async() -> None:
    for payload in (
        {"reward_first_pvc": -1},
        {"reward_second_pvc": 10_001},
        {"reward_third_pvc": 10_001},
    ):
        try:
            LaunchTournamentRequest(**payload)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Invalid custom prize accepted: {payload}")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        company = NatCompany(user_id=960001, name="Creator Cup Corp", specialization="miner")
        session.add(company)
        await session.flush()
        session.add(NatArmyUnit(company_id=company.id, unit_type="infantry", quantity=100))
        await session.commit()

        response = await CreatorService.launch_early_tournament(
            session, actor_id=777, rewards=(9, 8, 7), commit=False
        )
        tournament_id = response["result"]["tournament_id"]
        assert response["result"]["rewards_pvc"] == [9, 8, 7]
        tournament = await session.get(NatTournament, tournament_id)
        assert tournament.finish_time - tournament.start_time == timedelta(hours=18)
        audit = await session.scalar(
            select(NatCreatorAuditLog).where(NatCreatorAuditLog.target_id == str(tournament_id))
        )
        assert audit is not None and "9/8/7 PVC" in audit.details

        try:
            await CreatorService.launch_early_tournament(
                session, actor_id=777, rewards=(1, 2, 3), commit=False
            )
        except ValueError as exc:
            assert "active tournament" in str(exc)
        else:
            raise AssertionError("Second active custom tournament must be refused")

        for _ in range(3):
            await TournamentService.tick(session, tournament.finish_time)
        assert company.pvc_balance == 9
        reward_entries = await session.scalar(
            select(func.count(NatPremiumLedgerEntry.id)).where(
                NatPremiumLedgerEntry.operation_type == "tournament_reward",
                NatPremiumLedgerEntry.company_id == company.id,
            )
        )
        assert reward_entries == 1
        ledger = await CreatorService.get_premium_ledger(session, limit=10)
        assert ledger[0]["company_id"] == company.id
        assert ledger[0]["operation_type"] == "tournament_reward"
        assert ledger[0]["reason"]

    await engine.dispose()
    print("NATBIRZHA creator custom-tournament checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
