"""Post-60 mastery must remain useful, bounded and non-PvP."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.mastery_service import BRANCHES, MasteryService
from backend.natbirzha.services.progression_service import mastery_xp_required_for_rank, xp_required_for_level


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        rank = 8
        company = NatCompany(
            user_id=991001,
            name="Mastery Test",
            specialization="miner",
            level=60,
            xp=xp_required_for_level(60),
            mastery_rank=rank,
            mastery_xp=mastery_xp_required_for_rank(rank),
        )
        session.add(company)
        await session.flush()

        before = MasteryService.snapshot(company)
        assert before["points_available"] == rank
        result = await MasteryService.unlock(session, company, "doctrine")
        assert result["mastery"]["branches"]["doctrine"]["level"] == 1
        assert result["mastery"]["points_available"] == rank - 1
        assert 0 < MasteryService.effect(company, "doctrine") < BRANCHES["doctrine"]["cap"]
        assert MasteryService.node_cost(5) == 2

        # No mastery branch grants direct combat power: effects are economy/scouting only.
        assert set(BRANCHES) == {"industry", "logistics", "doctrine", "intelligence"}
        for branch in BRANCHES:
            setattr(company, f"mastery_{branch}", 10_000)
            assert MasteryService.effect(company, branch) < BRANCHES[branch]["cap"]

    await engine.dispose()
    print("NATBIRZHA mastery checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
