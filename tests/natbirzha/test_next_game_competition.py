import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameLedger
from backend.natbirzha.services.next_game_competition_service import NextGameCompetitionService
from backend.natbirzha.services.next_game_service import NextGameService


def test_next_game_competition_ranks_cash_level_and_real_last_day_production():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 10, 10, 12)
        async with sessions() as session:
            for tg_id, name in ((850_001, "Cash Corp"), (850_002, "Factory Corp"), (850_003, "XP Corp")):
                await NextGameService.create_company(session, tg_id, name)
            companies = list((await session.scalars(select(NatNextGameCompany).order_by(
                NatNextGameCompany.owner_tg_id
            ))).all())
            cash_corp, factory_corp, xp_corp = companies
            cash_corp.cash, factory_corp.cash, xp_corp.cash = 30_000, 20_000, 10_000
            factory_corp.level = 8
            xp_corp.level, xp_corp.xp = 12, 11_800
            session.add_all([
                NatNextGameLedger(
                    company_id=factory_corp.id, action="PRODUCTION_OUTPUT",
                    cash_company_delta=0, cash_treasury_delta=0,
                    item_id="energy", quantity_company_delta=100,
                    metadata_json={}, created_at=now - timedelta(hours=2),
                ),
                NatNextGameLedger(
                    company_id=cash_corp.id, action="PRODUCTION_OUTPUT",
                    cash_company_delta=0, cash_treasury_delta=0,
                    item_id="energy", quantity_company_delta=10,
                    metadata_json={}, created_at=now - timedelta(hours=30),
                ),
            ])
            await session.flush()

            ranking = await NextGameCompetitionService.snapshot(
                session, 850_002, now=now,
            )
            assert ranking["rankings"]["cash"]["leaders"][0]["name"] == "Cash Corp"
            assert ranking["rankings"]["cash"]["my_rank"]["rank"] == 2
            assert ranking["rankings"]["level"]["leaders"][0]["name"] == "XP Corp"
            assert ranking["rankings"]["production_24h"]["leaders"][0]["name"] == "Factory Corp"
            assert ranking["rankings"]["production_24h"]["leaders"][0]["value"] == 1_000
            assert ranking["rankings"]["production_24h"]["my_rank"]["rank"] == 1
            assert all(len(ranking["rankings"][key]["leaders"]) == 3 for key in (
                "cash", "level", "production_24h",
            ))

        await engine.dispose()

    asyncio.run(check())
