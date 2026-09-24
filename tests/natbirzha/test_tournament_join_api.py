"""HTTP coverage for joining an active NATBIRZHA tournament."""

import asyncio
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatTournament, NatTournamentParticipant
from backend.natbirzha.services.auth_service import get_current_company


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = get_game_now()
    async with sessions() as session:
        users = [
            User(tg_id=981001, full_name="Tournament Joiner", role="student"),
            User(tg_id=981002, full_name="Tournament Spectator", role="student"),
        ]
        session.add_all(users)
        await session.flush()
        companies = [
            NatCompany(user_id=users[0].id, name="Join API Corp", specialization="miner"),
            NatCompany(user_id=users[1].id, name="No Army Corp", specialization="agrarian"),
        ]
        session.add_all(companies)
        await session.flush()
        session.add(NatArmyUnit(company_id=companies[0].id, unit_type="infantry", quantity=20))
        tournament = NatTournament(
            tournament_number=1,
            start_time=now - timedelta(minutes=5),
            snapshot_time=now - timedelta(minutes=5),
            finish_time=now + timedelta(hours=17),
            status="PENDING",
            tournament_type="AUTO",
            prize_pool_nat=0,
        )
        session.add(tournament)
        await session.commit()
        company_ids = [company.id for company in companies]
        tournament_id = tournament.id

    app = FastAPI()
    app.include_router(natbirzha_router, prefix="/api")

    async def test_session():
        async with sessions() as session:
            yield session

    async def test_company(
        session: AsyncSession = Depends(get_db_session),
    ) -> NatCompany:
        return await session.scalar(select(NatCompany).where(NatCompany.id == company_ids[0]))

    app.dependency_overrides[get_db_session] = test_session
    app.dependency_overrides[get_current_company] = test_company

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        joined = await client.post(
            f"/api/natbirzha/military/tournaments/{tournament_id}/join",
            headers={"Idempotency-Key": "tournament-join-1"},
        )
        assert joined.status_code == 200, joined.text
        assert joined.json()["joined"] is True
        replay = await client.post(
            f"/api/natbirzha/military/tournaments/{tournament_id}/join",
            headers={"Idempotency-Key": "tournament-join-1"},
        )
        assert replay.status_code == 200 and replay.json() == joined.json()

        tournament_state = await client.get("/api/natbirzha/military/tournaments/current")
        assert tournament_state.json()["tournament"]["is_participant"] is True
        async with sessions() as session:
            participants = (
                await session.execute(
                    select(NatTournamentParticipant).where(
                        NatTournamentParticipant.tournament_id == tournament_id
                    )
                )
            ).scalars().all()
        assert [participant.company_id for participant in participants] == [company_ids[0]]

    screen = Path("frontend/natbirzha/js/screens/military_tournament.js").read_text(encoding="utf-8")
    api = Path("frontend/natbirzha/js/api.js").read_text(encoding="utf-8")
    assert "tournament-join-btn" in screen, "tournament view must expose a join action"
    assert "joinTournament:" in api, "NatAPI must expose the tournament join endpoint"

    await engine.dispose()
    print("NATBIRZHA tournament join HTTP checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
