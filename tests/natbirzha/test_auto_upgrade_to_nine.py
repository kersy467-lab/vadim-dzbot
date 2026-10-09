import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_auto_upgrade_service import BusinessAutoUpgradeService


def test_auto_upgrade_can_start_level_nine_but_never_level_ten():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 10, 10, 12, 0)

        async with sessions() as session:
            company = NatCompany(user_id=70001, name='Auto Upgrade Corp', specialization='miner', cash=10_000_000)
            session.add(company)
            await session.flush()
            business = NatBusiness(
                company_id=company.id,
                business_type='coal_open_pit',
                custom_name='Шахта',
                specialization='miner',
                stage=8,
                status='ACTIVE',
                last_settled_at=now,
                metadata_json={},
            )
            session.add(business)
            await session.commit()

            assert company.auto_upgrade_to_nine_enabled is False
            await BusinessAutoUpgradeService.set_enabled(session, company.id, True)
            started = await BusinessAutoUpgradeService.process_company(session, company.id, now=now)
            assert started['started_count'] == 1
            assert started['upgrades'][0]['target_stage'] == 9

            business.status = 'ACTIVE'
            business.upgrade_target_stage = None
            business.upgrade_ready_at = None
            business.stage = 9
            await session.flush()
            cash_at_level_nine = company.cash
            capped = await BusinessAutoUpgradeService.process_company(session, company.id, now=now)
            business = await session.scalar(select(NatBusiness).where(NatBusiness.id == business.id))

            assert capped['started_count'] == 0
            assert business.stage == 9
            assert business.status == 'ACTIVE'
            assert company.cash == cash_at_level_nine

        await engine.dispose()

    asyncio.run(check())
