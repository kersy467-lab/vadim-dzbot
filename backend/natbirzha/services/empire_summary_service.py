"""Server-owned read model for the NATBIRZHA 2.0 idle empire screen."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_rates import cash_business_rates
from backend.natbirzha.services.business_service import BusinessService


class EmpireSummaryService:
    """Builds presentation data without trusting the client with game formulas."""

    @staticmethod
    def _serialize_business(business: NatBusiness) -> dict[str, Any]:
        spec = get_business_spec(business.business_type)
        if spec is None:
            return {
                "id": business.id,
                "name": business.custom_name or business.business_type,
                "business_type": business.business_type,
                "stage": business.stage,
                "status": business.status,
                "catalog_missing": True,
            }

        rates = cash_business_rates(
            business, spec, upgrading=business.status == "UPGRADING"
        )
        next_upgrade = None
        if business.stage < int(spec["max_stage"]) and business.status == "ACTIVE":
            next_upgrade = BusinessService.upgrade_quote(spec, business.stage)
        return {
            "id": business.id,
            "name": business.custom_name or spec["name"],
            "business_type": business.business_type,
            "specialization": business.specialization,
            "stage": business.stage,
            "max_stage": spec["max_stage"],
            "status": business.status,
            "slot_weight": business.slot_weight,
            "gross_per_hour": round(rates.gross_per_hour, 2),
            "maintenance_per_hour": round(rates.maintenance_per_hour, 2),
            "net_per_hour": round(rates.net_per_hour, 2),
            "inputs_per_hour": spec["inputs_per_hour"],
            "outputs_per_hour": spec["outputs_per_hour"],
            "upgrade_ready_at": business.upgrade_ready_at,
            "next_upgrade": next_upgrade,
        }

    @classmethod
    async def build(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        company = await session.scalar(select(NatCompany).where(NatCompany.id == company_id))
        if company is None:
            raise ValueError("Company not found")
        businesses = list((await session.execute(
            select(NatBusiness)
            .where(NatBusiness.company_id == company.id)
            .order_by(NatBusiness.created_at, NatBusiness.id)
        )).scalars().all())
        serialized = [cls._serialize_business(business) for business in businesses]
        used_slots = sum(
            int(business.slot_weight) for business in businesses if business.status != "BANKRUPT"
        )
        gross = sum(item.get("gross_per_hour", 0.0) for item in serialized)
        expenses = sum(item.get("maintenance_per_hour", 0.0) for item in serialized)
        return {
            "company_id": company.id,
            "cash": round(float(company.cash), 2),
            "income_per_hour": round(gross, 2),
            "expenses_per_hour": round(expenses, 2),
            "net_cash_per_hour": round(gross - expenses, 2),
            "slots": BusinessService.business_slot_limits(
                level=company.level, territory_tiles=company.territory_tiles, used=used_slots
            ),
            "businesses": serialized,
            "generated_at": normalize_dt(now or get_game_now()),
        }


__all__ = ["EmpireSummaryService"]
