"""Availability rules for company specializations."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import INDUSTRIES
from backend.natbirzha.models.company import NatCompany


class IndustrySelectionService:
    """Report which industries may be selected during company creation/respec."""

    RARE_INDUSTRY_ID = "brewery"

    @staticmethod
    async def _company_counts(session: AsyncSession) -> dict[str, int]:
        rows = (await session.execute(
            select(NatCompany.specialization, func.count(NatCompany.id))
            .group_by(NatCompany.specialization)
        )).all()
        return {str(specialization): int(count) for specialization, count in rows}

    @classmethod
    def _availability_for_counts(
        cls,
        specialization: str,
        counts: dict[str, int],
    ) -> dict[str, Any]:
        industry_id = str(specialization or "").strip().lower()
        industry = INDUSTRIES.get(industry_id)
        if industry_id != cls.RARE_INDUSTRY_ID and industry is None:
            return {
                "specialization": industry_id,
                "available": False,
                "company_count": counts.get(industry_id, 0),
                "missing_industries": [],
                "reason": f"Неизвестная отрасль «{industry_id or '—'}». Выберите отрасль из списка.",
            }

        name = str(
            (industry or {}).get(
                "name",
                "Пивоварня" if industry_id == cls.RARE_INDUSTRY_ID else industry_id,
            )
        )
        missing_industries: list[str] = []
        if industry_id == cls.RARE_INDUSTRY_ID:
            reason = "Пивоварение открыто для выбора."
        else:
            reason = f"Отрасль «{name}» доступна для выбора."

        return {
            "specialization": industry_id,
            "available": not missing_industries,
            "company_count": counts.get(industry_id, 0),
            "missing_industries": missing_industries,
            "reason": reason,
        }

    @classmethod
    async def get_availability(
        cls,
        session: AsyncSession,
        specialization: str,
    ) -> dict[str, Any]:
        counts = await cls._company_counts(session)
        return cls._availability_for_counts(specialization, counts)

    @classmethod
    async def get_selection_options(cls, session: AsyncSession) -> list[dict[str, Any]]:
        """Return the current catalog industries with availability and reasons."""
        counts = await cls._company_counts(session)
        return [
            cls._availability_for_counts(industry_id, counts)
            for industry_id in INDUSTRIES
        ]

__all__ = ["IndustrySelectionService"]
