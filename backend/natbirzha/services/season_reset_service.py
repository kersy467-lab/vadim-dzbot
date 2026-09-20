"""Safe all-company reset. It is deliberately inert until the route enables it."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog, NatStateBond
from backend.natbirzha.models.military import NatTournament
from backend.natbirzha.models.season import NatSeasonResetOperation
from backend.natbirzha.services.access_control import is_creator_user
from backend.natbirzha.services.company_service import CompanyService


class SeasonResetService:
    @staticmethod
    async def preview(session: AsyncSession) -> dict:
        rows = (await session.execute(select(NatCompany, User).join(User, User.id == NatCompany.user_id))).all()
        return {
            "affected_companies": len(rows),
            "creator_companies": sum(1 for _company, user in rows if is_creator_user(user)),
            "normal_starting_cash": nat_settings.STARTING_CASH,
            "creator_starting_cash": nat_settings.CREATOR_STARTING_CASH,
            "tester_starting_pvc": nat_settings.TESTER_STARTING_PVC,
        }

    @classmethod
    async def execute(
        cls,
        session: AsyncSession,
        *,
        operation_id: str,
        actor_tg_id: int,
        backup_reference: str,
    ) -> dict:
        if not operation_id or len(operation_id) > 120:
            raise ValueError("A 1–120 character reset operation ID is required")
        if not backup_reference or len(backup_reference) > 255:
            raise ValueError("A verified backup reference is required before reset")
        existing = await session.scalar(
            select(NatSeasonResetOperation).where(NatSeasonResetOperation.operation_id == operation_id)
        )
        if existing is not None:
            return {
                "status": existing.status.lower(),
                "operation_id": existing.operation_id,
                "affected_companies": existing.affected_companies,
                "replayed": True,
            }

        rows = (await session.execute(select(NatCompany, User).join(User, User.id == NatCompany.user_id))).all()
        operation = NatSeasonResetOperation(
            operation_id=operation_id,
            actor_tg_id=actor_tg_id,
            backup_reference=backup_reference,
            affected_companies=len(rows),
            status="RUNNING",
        )
        session.add(operation)
        await session.flush()

        # First clear per-company records with the existing exhaustive reset logic.
        # The Telegram user rows survive, so permissions and identities are retained.
        blueprints = [(company.user_id, company.name, company.specialization) for company, _user in rows]
        for user_id, _name, _specialization in blueprints:
            await CompanyService.reset_company_for_user(session, user_id, commit=False)

        # A season owns its event and government issue state; player-owned rows
        # have already been removed above before their parent records disappear.
        await session.execute(delete(NatTournament))
        await session.execute(delete(NatStateBond))

        # Reuse the normal onboarding routine so reset players receive their
        # starter factory, inventory, garrison and role-based grants.
        for user_id, name, specialization in blueprints:
            await CompanyService.create_company(
                session, user_id, name, specialization, commit=False
            )
        operation.status = "COMPLETED"
        operation.completed_at = datetime.utcnow()
        session.add(NatCreatorAuditLog(
            actor_id=actor_tg_id,
            action="SEASON_RESET",
            target_type="natbirzha_season",
            target_id=operation_id,
            details=(f"Сброшено компаний: {len(blueprints)}; backup: {backup_reference}"),
        ))
        await session.commit()
        return {
            "status": "completed",
            "operation_id": operation_id,
            "affected_companies": len(blueprints),
            "replayed": False,
        }


__all__ = ["SeasonResetService"]
