"""Creator grants are self-only by construction and fully audited."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.services.creator_grant_service import CreatorGrantService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        creator = User(tg_id=991004, full_name="Creator", role="admin")
        normal = User(tg_id=991005, full_name="Player", role="student")
        session.add_all([creator, normal])
        await session.flush()
        own = NatCompany(user_id=creator.id, name="Creator Corp", specialization="miner", cash=0, pvc_balance=0)
        other = NatCompany(user_id=normal.id, name="Other Corp", specialization="miner", cash=0, pvc_balance=0)
        session.add_all([own, other])
        await session.flush()

        result = await CreatorGrantService.grant_to_self(session, creator, cash=200_000, pvc=150)
        assert result["company_id"] == own.id
        assert result["cash_after"] == 200_000
        assert result["pvc_after"] == 150
        assert other.cash == 0 and other.pvc_balance == 0
        audit = await session.scalar(select(NatCreatorAuditLog).where(NatCreatorAuditLog.action == "SELF_GRANT"))
        assert audit is not None and audit.target_id == str(own.id)

        try:
            await CreatorGrantService.grant_to_self(session, normal, cash=1)
        except PermissionError:
            pass
        else:
            raise AssertionError("Normal player must never use creator self-grant")

    await engine.dispose()
    print("NATBIRZHA creator controls checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
