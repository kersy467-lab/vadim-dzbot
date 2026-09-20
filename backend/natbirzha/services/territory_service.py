"""Server-priced territory growth for the bounded NATBIRZHA 2.0 business grid."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService


class TerritoryService:
    BASE_COST = 15_000.0
    COST_GROWTH = 1.25
    STARTING_TILES = 4

    @classmethod
    def quote(cls, company: NatCompany) -> dict[str, Any]:
        owned = max(cls.STARTING_TILES, int(company.territory_tiles or cls.STARTING_TILES))
        cost = round(cls.BASE_COST * (cls.COST_GROWTH ** (owned - cls.STARTING_TILES)), 2)
        return {"current_tiles": owned, "next_tiles": owned + 1, "cost": cost}

    @classmethod
    async def expand(cls, session: AsyncSession, company_id: int) -> dict[str, Any]:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Company not found")
        quote = cls.quote(company)
        if float(company.cash) < quote["cost"]:
            raise ValueError("Insufficient cash to expand territory")
        company.cash = round(float(company.cash) - quote["cost"], 2)
        company.territory_tiles = quote["next_tiles"]
        await session.flush()
        return {
            "success": True,
            "cost": quote["cost"],
            "new_tiles": company.territory_tiles,
            "remaining_cash": company.cash,
            "slots": BusinessService.business_slot_limits(
                level=company.level, territory_tiles=company.territory_tiles, used=0
            ),
        }


__all__ = ["TerritoryService"]
