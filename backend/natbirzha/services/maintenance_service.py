"""Service for managing Natbirzha maintenance mode state."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import ClassSetting

MAINTENANCE_SETTING_KEY = "natbirzha_maintenance_mode"


class MaintenanceService:
    @classmethod
    async def is_maintenance_active(cls, session: AsyncSession) -> bool:
        result = await session.execute(
            select(ClassSetting).where(ClassSetting.key == MAINTENANCE_SETTING_KEY)
        )
        row = result.scalar_one_or_none()
        if not row or not row.value:
            return False
        return row.value.strip().lower() in ("true", "1", "yes", "on")

    @classmethod
    async def set_maintenance_active(cls, session: AsyncSession, enabled: bool) -> bool:
        result = await session.execute(
            select(ClassSetting).where(ClassSetting.key == MAINTENANCE_SETTING_KEY)
        )
        row = result.scalar_one_or_none()
        val = "true" if enabled else "false"
        if row:
            row.value = val
        else:
            session.add(ClassSetting(key=MAINTENANCE_SETTING_KEY, value=val))
        await session.commit()
        return enabled

    @classmethod
    async def toggle_maintenance(cls, session: AsyncSession) -> bool:
        current = await cls.is_maintenance_active(session)
        new_val = not current
        await cls.set_maintenance_active(session, new_val)
        return new_val


__all__ = ["MaintenanceService", "MAINTENANCE_SETTING_KEY"]
