"""Explicit, idempotent seasonal reset preserves Telegram identities and creator grant."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.models.season import NatSeasonResetOperation
from backend.natbirzha.services.season_reset_service import SeasonResetService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        creator = User(tg_id=991001, full_name="Creator", role="admin")
        tester = User(tg_id=991002, full_name="Tester", is_tester=True)
        player = User(tg_id=991003, full_name="Player")
        session.add_all([creator, tester, player])
        await session.flush()

        # New companies and seasonal restarts must use the same grant policy.
        direct_creator = await CompanyService.create_company(session, creator.id, "Direct Creator", "miner", commit=False)
        direct_tester = await CompanyService.create_company(session, tester.id, "Direct Tester", "forester", commit=False)
        direct_player = await CompanyService.create_company(session, player.id, "Direct Player", "agrarian", commit=False)
        assert direct_creator.cash == 500_000 and direct_creator.pvc_balance == 200
        assert direct_tester.cash == 50_000 and direct_tester.pvc_balance == 200
        assert direct_player.cash == 50_000 and direct_player.pvc_balance == 0
        await CompanyService.reset_company_for_user(session, creator.id, commit=False)
        await CompanyService.reset_company_for_user(session, tester.id, commit=False)
        await CompanyService.reset_company_for_user(session, player.id, commit=False)

        old_creator = NatCompany(user_id=creator.id, name="Creator Corp", specialization="miner", cash=999)
        old_tester = NatCompany(user_id=tester.id, name="Tester Corp", specialization="forester", cash=999)
        old_player = NatCompany(user_id=player.id, name="Player Corp", specialization="forester", cash=999)
        session.add_all([old_creator, old_tester, old_player])
        await session.flush()
        session.add(NatFactory(company_id=old_player.id, building_type="sawmill", specialization="forester"))
        await session.commit()

        preview = await SeasonResetService.preview(session)
        assert preview["affected_companies"] == 3 and preview["creator_companies"] == 1
        result = await SeasonResetService.execute(
            session, operation_id="season-test-001", actor_tg_id=creator.tg_id, backup_reference="test-backup"
        )
        assert result["status"] == "completed" and result["affected_companies"] == 3
        companies = (await session.execute(select(NatCompany).order_by(NatCompany.name))).scalars().all()
        assert len(companies) == 3
        by_name = {company.name: company for company in companies}
        assert by_name["Creator Corp"].cash == 500_000
        assert by_name["Creator Corp"].pvc_balance == 200
        assert by_name["Tester Corp"].cash == 50_000
        assert by_name["Tester Corp"].pvc_balance == 200
        assert by_name["Player Corp"].cash == 50_000
        assert by_name["Player Corp"].level == 1 and by_name["Player Corp"].territory_tiles == 4
        assert len((await session.execute(select(NatFactory))).scalars().all()) == 0
        assert len((await session.execute(select(NatBusiness))).scalars().all()) == 3
        replay = await SeasonResetService.execute(
            session, operation_id="season-test-001", actor_tg_id=creator.tg_id, backup_reference="test-backup"
        )
        assert replay["replayed"] is True
        assert (await session.execute(select(NatSeasonResetOperation))).scalars().one().status == "COMPLETED"
    await engine.dispose()
    print("NATBIRZHA controlled season reset: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
