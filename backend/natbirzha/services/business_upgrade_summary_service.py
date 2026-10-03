"""Small read model for the business upgrade screen."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.services.business_service import BusinessService


class BusinessUpgradeSummaryService:
    @staticmethod
    async def input_item_ids(session: AsyncSession, company_id: int) -> dict[str, list[str]]:
        business_types = (await session.execute(
            select(NatBusiness.business_type, NatBusiness.status)
            .where(NatBusiness.company_id == company_id, NatBusiness.status != "MERGING")
        )).all()
        item_ids: set[str] = set()
        for business_type, _status in business_types:
            spec = get_business_spec(business_type)
            if not spec or spec.get("legacy_hidden", False):
                continue
            item_ids.update(spec.get("inputs_per_hour", {}).keys())
        return {"items": sorted(item_ids)}

    @staticmethod
    async def build(session: AsyncSession, company_id: int) -> dict[str, list[dict[str, Any]]]:
        businesses = (await session.execute(
            select(NatBusiness)
            .where(NatBusiness.company_id == company_id)
            .order_by(NatBusiness.created_at, NatBusiness.id)
        )).scalars().all()
        upgradeable_statuses = {
            "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY",
            "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
        }
        result = []
        for business in businesses:
            spec = get_business_spec(business.business_type)
            if (spec or {}).get("legacy_hidden", False) or business.status == "MERGING":
                continue
            contract_expired = bool((business.metadata_json or {}).get("contract_expired"))
            next_upgrade = None
            if spec and business.stage < int(spec["max_stage"]) and business.status in upgradeable_statuses:
                next_upgrade = BusinessService.upgrade_quote(spec, business.stage)
            if contract_expired:
                next_upgrade = None
            result.append({
                "id": business.id,
                "name": business.custom_name or (spec["name"] if spec else "Неизвестное предприятие"),
                "catalog_name": spec["name"] if spec else "Неизвестное предприятие",
                "specialization": business.specialization,
                "stage": business.stage,
                "max_stage": spec["max_stage"] if spec else business.stage,
                "status": business.status,
                "contract_expired": contract_expired,
                "next_upgrade": next_upgrade,
            })
        return {"businesses": result}


__all__ = ["BusinessUpgradeSummaryService"]
