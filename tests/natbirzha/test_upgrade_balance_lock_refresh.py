"""Guard upgrade affordability against stale company rows after lock waits."""

import asyncio

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.upgrade_service import UpgradeService


def test_legacy_upgrade_uses_latest_locked_company_balance() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=72_001,
                name="Concurrent Upgrade Corp",
                specialization="power_engineer",
                level=10,
                cash=10_000,
            )
            session.add(company)
            await session.flush()
            factory = NatFactory(
                company_id=company.id,
                building_type="solar_plant",
                specialization="power_engineer",
                level=1,
                workers=10,
            )
            session.add(factory)
            await session.commit()

            company = await session.get(NatCompany, company.id)
            assert company is not None and company.cash == 10_000

            # Model a concurrent request committing a lower balance after this
            # request loaded its company identity into the SQLAlchemy session.
            await session.execute(
                update(NatCompany)
                .where(NatCompany.id == company.id)
                .values(cash=100)
                .execution_options(synchronize_session=False)
            )
            assert company.cash == 10_000

            with pytest.raises(ValueError, match="cash"):
                await UpgradeService.upgrade(session, company, factory.id, "workers")

            await session.rollback()

        await engine.dispose()

    asyncio.run(check())
