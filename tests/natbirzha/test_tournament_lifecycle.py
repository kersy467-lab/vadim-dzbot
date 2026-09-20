"""72-hour cadence, 18-hour tournament, ranking, and PVC rewards."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.alliances import NatAlliance, NatAllianceMember
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatTournamentParticipant
from backend.natbirzha.services.tournament_service import TournamentService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        companies = [
            NatCompany(user_id=940000 + i, name=f"Tournament Corp {i}", specialization="miner")
            for i in range(1, 4)
        ]
        session.add_all(companies)
        await session.flush()
        session.add_all(
            [
                NatArmyUnit(company_id=companies[0].id, unit_type="infantry", quantity=100),
                NatArmyUnit(company_id=companies[1].id, unit_type="infantry", quantity=50),
                NatArmyUnit(company_id=companies[2].id, unit_type="infantry", quantity=50),
            ]
        )
        alliance = NatAlliance(
            name="Tournament Alliance", leader_company_id=companies[0].id, member_count=1
        )
        session.add(alliance)
        await session.flush()
        session.add(
            NatAllianceMember(
                alliance_id=alliance.id, company_id=companies[0].id, role="LEADER"
            )
        )
        await session.commit()

        now = datetime(2026, 9, 19, 9, 0, 0)
        tournament = await TournamentService.ensure_next_scheduled(session, now)
        assert tournament.start_time == now
        assert tournament.finish_time == now + timedelta(hours=18)
        assert (tournament.reward_first_pvc, tournament.reward_second_pvc, tournament.reward_third_pvc) == (
            150, 100, 70
        )

        activated = await TournamentService.activate_due(session, now)
        assert [row.id for row in activated] == [tournament.id]
        assert tournament.status == "ACTIVE"
        participants = (
            await session.execute(
                select(NatTournamentParticipant).where(
                    NatTournamentParticipant.tournament_id == tournament.id
                )
            )
        ).scalars().all()
        assert len(participants) == 3
        by_company = {participant.company_id: participant for participant in participants}
        assert by_company[companies[0].id].alliance_id == alliance.id
        assert by_company[companies[1].id].alliance_id is None

        result = await TournamentService.resolve(
            session, tournament.id, now=tournament.finish_time
        )
        assert result["status"] == "completed"
        assert [row["rank"] for row in result["ranking"]] == [1, 2, 2]
        assert [row["prize_pvc"] for row in result["ranking"]] == [150, 100, 100]
        assert [company.pvc_balance for company in companies] == [150, 100, 100]

        replay = await TournamentService.resolve(
            session, tournament.id, now=tournament.finish_time + timedelta(minutes=1)
        )
        assert replay == result
        assert [company.pvc_balance for company in companies] == [150, 100, 100]

        next_tournament = await TournamentService.ensure_next_scheduled(
            session, now + timedelta(hours=19)
        )
        assert next_tournament.start_time == now + timedelta(hours=72)
        assert next_tournament.finish_time == now + timedelta(hours=90)

        custom = await TournamentService.create_custom(
            session,
            now=now + timedelta(hours=100),
            created_by_user_id=999,
            rewards=(9, 8, 7),
        )
        assert custom.status == "ACTIVE"
        assert custom.tournament_type == "CUSTOM"
        assert (custom.reward_first_pvc, custom.reward_second_pvc, custom.reward_third_pvc) == (9, 8, 7)

    await engine.dispose()
    print("NATBIRZHA tournament lifecycle checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
