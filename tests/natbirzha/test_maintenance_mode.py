"""Tests for Natbirzha maintenance mode service and toggle behavior."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.db.models import Base, ClassSetting
from backend.natbirzha.services.maintenance_service import (
    LEGACY_MAINTENANCE_SETTING_KEY,
    MAINTENANCE_SETTING_KEY,
    MaintenanceService,
)


def test_maintenance_service_lifecycle():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as session:
            # 1. Default should be False (inactive)
            active = await MaintenanceService.is_maintenance_active(session, default=False)
            assert active is False

            # 2. Toggle ON
            new_val = await MaintenanceService.toggle_maintenance(session, default=False)
            assert new_val is True
            assert await MaintenanceService.is_maintenance_active(session) is True

            # 3. Toggle OFF
            new_val = await MaintenanceService.toggle_maintenance(session, default=False)
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


def test_maintenance_fallback_reads_both_keys_in_one_query():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        select_statements = []

        def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().lower().startswith("select"):
                select_statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", count_selects)
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with sessions() as session:
                session.add(ClassSetting(key=LEGACY_MAINTENANCE_SETTING_KEY, value="true"))
                await session.commit()

                assert await MaintenanceService.is_maintenance_active(session, default=False) is True
                assert len(select_statements) == 1

                # The explicit primary key overrides the legacy value, including false.
                session.add(ClassSetting(key=MAINTENANCE_SETTING_KEY, value="false"))
                await session.commit()
                select_statements.clear()
                assert await MaintenanceService.is_maintenance_active(session, default=True) is False
                assert len(select_statements) == 1

                await session.delete(await session.get(ClassSetting, MAINTENANCE_SETTING_KEY))
                legacy_setting = await session.get(ClassSetting, LEGACY_MAINTENANCE_SETTING_KEY)
                legacy_setting.value = "false"
                await session.commit()
                select_statements.clear()
                assert await MaintenanceService.is_maintenance_active(session, default=True) is True
                assert len(select_statements) == 1
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_selects)
            await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_maintenance_service_lifecycle()
    print("test_maintenance_mode: PASS")
