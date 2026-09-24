"""Paid, validated company name changes."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany


class CompanyRenameService:
    RENAME_COST = 10_000.0
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 64

    @classmethod
    async def rename(
        cls,
        session: AsyncSession,
        company_id: int,
        requested_name: str,
    ) -> dict[str, Any]:
        clean_name = str(requested_name or "").strip()
        if not clean_name:
            raise ValueError("Введите новое название компании.")
        if not cls.MIN_NAME_LENGTH <= len(clean_name) <= cls.MAX_NAME_LENGTH:
            raise ValueError("Название компании должно содержать от 2 до 64 символов.")
        if "<" in clean_name or ">" in clean_name:
            raise ValueError("Название компании не должно содержать HTML-разметку.")

        company = (await session.execute(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )).scalar_one_or_none()
        if company is None:
            raise ValueError("Компания не найдена.")
        if clean_name == company.name:
            raise ValueError("Новое название совпадает с текущим.")

        duplicate_id = await session.scalar(
            select(NatCompany.id).where(
                NatCompany.name == clean_name,
                NatCompany.id != company.id,
            ).limit(1)
        )
        if duplicate_id is not None:
            raise ValueError("Это название уже занято другой компанией.")

        if company.cash < cls.RENAME_COST:
            raise ValueError(
                f"Недостаточно cash для смены названия: нужно {cls.RENAME_COST:.0f}, "
                f"доступно {company.cash:.2f}."
            )

        company.name = clean_name
        company.cash = round(float(company.cash) - cls.RENAME_COST, 2)
        await session.flush()
        return {
            "success": True,
            "name": company.name,
            "cash": company.cash,
            "cost_paid": cls.RENAME_COST,
        }


__all__ = ["CompanyRenameService"]
