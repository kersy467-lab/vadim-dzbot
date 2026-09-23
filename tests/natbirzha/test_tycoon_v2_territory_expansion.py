"""Territory still has its own price and does not grant business slots."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.territory_service import TerritoryService


def test_territory_expansion_keeps_price_but_does_not_change_business_capacity() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(user_id=9_701, name="Territory Corp", specialization="retail", cash=20_000)
            company.territory_tiles = 4
            session.add(company)
            await session.commit()

            assert TerritoryService.quote(company)["cost"] == 15_000.0
            result = await TerritoryService.expand(session, company.id)
            assert result["new_tiles"] == 5
            assert result["cost"] == 15_000.0
            assert result["slots"]["max"] == 10

        await engine.dispose()

    asyncio.run(check())
