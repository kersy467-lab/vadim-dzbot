"""Tests for Natbirzha maintenance mode service and toggle behavior."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.db.models import Base
from backend.natbirzha.services.maintenance_service import MaintenanceService


def test_maintenance_service_lifecycle():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as session:
            # 1. Default should be False (inactive)
            active = await MaintenanceService.is_maintenance_active(session)
            assert active is False

            # 2. Toggle ON
            new_val = await MaintenanceService.toggle_maintenance(session)
            assert new_val is True
            assert await MaintenanceService.is_maintenance_active(session) is True

            # 3. Toggle OFF
            new_val = await MaintenanceService.toggle_maintenance(session)
            assert new_val is False
            assert await MaintenanceService.is_maintenance_active(session) is False

            # 4. Explicit set True
            await MaintenanceService.set_maintenance_active(session, True)
            assert await MaintenanceService.is_maintenance_active(session) is True

            # 5. Explicit set False
            await MaintenanceService.set_maintenance_active(session, False)
            assert await MaintenanceService.is_maintenance_active(session) is False

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_maintenance_service_lifecycle()
    print("test_maintenance_mode: PASS")
