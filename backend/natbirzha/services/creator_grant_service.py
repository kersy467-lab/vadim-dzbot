"""Creator-only self grants for testing without arbitrary player minting."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.services.access_control import is_creator_user
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


class CreatorGrantService:
    MAX_CASH_PER_GRANT = 10_000_000.0
    MAX_PVC_PER_GRANT = 10_000

    @classmethod
    async def grant_to_self(
        cls, session: AsyncSession, creator: User, *, cash: float = 0.0, pvc: int = 0
    ) -> dict:
        cash = round(float(cash or 0.0), 2)
        pvc = int(pvc or 0)
        if not is_creator_user(creator):
            raise PermissionError("Creator access required")
        if cash < 0 or pvc < 0 or (cash == 0 and pvc == 0):
            raise ValueError("Укажите положительное начисление cash или PVC")
        if cash > cls.MAX_CASH_PER_GRANT or pvc > cls.MAX_PVC_PER_GRANT:
            raise ValueError("Начисление превышает безопасный лимит одной операции")
        company = await session.scalar(
            select(NatCompany).where(NatCompany.user_id == creator.id).with_for_update()
        )
        if company is None:
            raise ValueError("У Создателя нет компании в НАТБИРЖЕ")

        cash_before = float(company.cash or 0.0)
        pvc_before = int(company.pvc_balance or 0)
        company.cash = round(cash_before + cash, 2)
        company.pvc_balance = pvc_before + pvc
        if cash:
            await EconomyMetricsService.record(
                session,
                company_id=company.id,
                flow="SOURCE",
                category="creator_self_grant",
                cash_amount=cash,
                context={"actor_tg_id": creator.tg_id},
            )
        session.add(NatCreatorAuditLog(
            actor_id=creator.tg_id,
            action="SELF_GRANT",
            target_type="company",
            target_id=str(company.id),
            details=f"cash +{cash:.2f}; PVC +{pvc}; self-only",
            created_at=get_game_now(),
        ))
        await session.flush()
        return {
            "success": True,
            "company_id": company.id,
            "cash_before": round(cash_before, 2),
            "cash_after": company.cash,
            "pvc_before": pvc_before,
            "pvc_after": company.pvc_balance,
        }


__all__ = ["CreatorGrantService"]
