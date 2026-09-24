"""Creator-only hard reset of all mutable NATBIRZHA game state.

The school-bot ``users`` table is intentionally outside this reset. That keeps
Telegram identity, the admin role and ``is_tester`` flags intact while every
NATBIRZHA profile and mutable world row is removed.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401 - register every NAT table in Base.metadata
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.services.access_control import is_creator_user


class WorldResetService:
    """Erase all mutable NATBIRZHA state without touching global user records."""

    CONFIRMATION_PHRASE = "СБРОСИТЬ НАТБИРЖУ"
    # These rows are catalogs/reference data rather than player/world progress.
    PRESERVED_TABLES = {
        "nat_pve_corporations",
        "nat_reference_rate_snapshots",
    }

    @classmethod
    def resettable_tables(cls):
        return [
            table
            for table in reversed(Base.metadata.sorted_tables)
            if table.name.startswith("nat_") and table.name not in cls.PRESERVED_TABLES
        ]

    @staticmethod
    async def preview(session: AsyncSession) -> dict:
        rows = (
            await session.execute(
                select(NatCompany, User).join(User, User.id == NatCompany.user_id)
            )
        ).all()
        tester_companies = sum(1 for _company, user in rows if bool(user.is_tester))
        creator_companies = sum(1 for _company, user in rows if is_creator_user(user))
        total_users = await session.scalar(select(func.count(User.id))) or 0
        return {
            "affected_companies": len(rows),
            "creator_companies": creator_companies,
            "tester_companies": tester_companies,
            "global_users_preserved": int(total_users),
            "normal_starting_cash": nat_settings.STARTING_CASH,
            "creator_starting_cash": nat_settings.STARTING_CASH,
            "tester_starting_pvc": nat_settings.TESTER_STARTING_PVC,
            "confirmation_phrase": WorldResetService.CONFIRMATION_PHRASE,
        }

    @classmethod
    async def execute(
        cls,
        session: AsyncSession,
        *,
        actor_tg_id: int,
        confirmation: str,
    ) -> dict:
        if confirmation.strip() != cls.CONFIRMATION_PHRASE:
            raise ValueError(
                f'Для полного сброса введите точно: {cls.CONFIRMATION_PHRASE}'
            )

        preview = await cls.preview(session)
        affected_companies = int(preview["affected_companies"])

        # Reverse metadata order deletes children before parents and makes the
        # reset independent of database-specific ON DELETE behaviour.
        cleared_tables: list[str] = []
        for table in cls.resettable_tables():
            await session.execute(delete(table))
            cleared_tables.append(table.name)

        # The audit table was intentionally cleared above: this is the first
        # audit record of the new NATBIRZHA world. It contains no player profile.
        session.add(
            NatCreatorAuditLog(
                actor_id=actor_tg_id,
                action="WORLD_RESET",
                target_type="natbirzha_world",
                target_id="all",
                details=(
                    f"Полный сброс НАТБИРЖИ: удалено компаний {affected_companies}. "
                    "Глобальные users, admin-role и is_tester сохранены."
                ),
            )
        )
        await session.commit()
        return {
            "status": "completed",
            "affected_companies": affected_companies,
            "cleared_tables": len(cleared_tables),
            "users_preserved": int(preview["global_users_preserved"]),
            "next_start": {
                "creator_cash": nat_settings.STARTING_CASH,
                "normal_cash": nat_settings.STARTING_CASH,
                "tester_pvc": nat_settings.TESTER_STARTING_PVC,
            },
        }

    @classmethod
    async def execute_startup_reset(
        cls,
        session: AsyncSession,
        *,
        actor_tg_id: int = 1053722876,
        marker: str = "world-reset-v20260920",
    ) -> dict:
        """One-time startup world reset: wipes all existing companies and starts fresh."""
        cleared_tables: list[str] = []
        for table in cls.resettable_tables():
            await session.execute(delete(table))
            cleared_tables.append(table.name)

        # Ensure creator exists and is elevated
        res = await session.execute(select(User).where(User.tg_id == actor_tg_id))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                tg_id=actor_tg_id,
                username="creator",
                full_name="Создатель",
                role="admin",
                is_tester=True,
            )
            session.add(user)
        else:
            user.role = "admin"
            user.is_tester = True

        session.add(
            NatCreatorAuditLog(
                actor_id=actor_tg_id,
                action="WORLD_RESET",
                target_type="natbirzha_world",
                target_id=marker,
                details=(
                    f"Автоматический сброс НАТБИРЖИ на старте: очищено таблиц {len(cleared_tables)}. "
                    "Все старые профили компаний удалены. Игра начинается с нуля."
                ),
            )
        )
        await session.commit()
        return {
            "status": "completed",
            "cleared_tables": len(cleared_tables),
            "marker": marker,
        }


__all__ = ["WorldResetService"]
