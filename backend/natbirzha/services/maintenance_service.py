"""Service for managing Natbirzha maintenance mode state."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import ClassSetting
from backend.natbirzha.config import nat_settings

MAINTENANCE_SETTING_KEY = "natbirzha_game_access_closed"
LEGACY_MAINTENANCE_SETTING_KEY = "natbirzha_maintenance_mode"


class MaintenanceService:
    @classmethod
    async def is_maintenance_active(
        cls,
        session: AsyncSession,
        *,
        default: bool | None = None,
    ) -> bool:
        """Return the persisted gate state, falling back to the launch setting.

        The environment value supplies the initial state on a fresh database.
        Once an admin changes it, the database value survives deploys and can
        explicitly override that initial default.
        """
        result = await session.execute(
            select(ClassSetting).where(ClassSetting.key == MAINTENANCE_SETTING_KEY)
        )
        row = result.scalar_one_or_none()
        if row and row.value:
            return row.value.strip().lower() in ("true", "1", "yes", "on")

        # The old key controlled only a frontend notice. Preserve an active
        # legacy break, but do not let its old "false" value override the new
        # launch-only default on a fresh rollout.
        legacy_result = await session.execute(
            select(ClassSetting).where(ClassSetting.key == LEGACY_MAINTENANCE_SETTING_KEY)
        )
        legacy_row = legacy_result.scalar_one_or_none()
        legacy_active = bool(
            legacy_row
            and legacy_row.value
            and legacy_row.value.strip().lower() in ("true", "1", "yes", "on")
        )
        if legacy_active:
            return True
        return bool(nat_settings.ADMIN_ONLY_ACCESS if default is None else default)

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
    async def toggle_maintenance(
        cls,
        session: AsyncSession,
        *,
        default: bool | None = None,
    ) -> bool:
        current = await cls.is_maintenance_active(session, default=default)
        new_val = not current
        await cls.set_maintenance_active(session, new_val)
        return new_val


__all__ = ["MaintenanceService", "MAINTENANCE_SETTING_KEY", "LEGACY_MAINTENANCE_SETTING_KEY"]
