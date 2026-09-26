"""Catalog-backed sector and production-rate selection for city orders."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES, INDUSTRIES, starter_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.industry_upgrade_service import IndustryUpgradeService


PAUSED_STATUSES = frozenset({
    "PAUSED_MANUAL", "PAUSED_SUPPLY", "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
    "BANKRUPT", "MERGING",
})


def active_city_order_industries() -> list[str]:
    """Use only currently visible production industries; no fixed industry count."""
    catalog_sectors = {
        str(spec.get("specialization")) for spec in CAREER_BUSINESSES.values()
        if not spec.get("legacy_hidden") and spec.get("specialization")
    }
    return sorted(str(sector) for sector in set(INDUSTRIES).intersection(catalog_sectors))


def primary_output(industry: str) -> tuple[str, dict] | None:
    starter = starter_business_spec(industry)
    if not starter:
        return None
    for item_id in sorted(starter.get("outputs_per_hour", {})):
        item = CANONICAL_ITEMS.get(item_id)
        if item and float(item.get("base_price") or 0) > 0:
            return item_id, starter
    return None


async def sector_output_rate(
    session: AsyncSession, industry: str, item_id: str, starter: dict,
) -> float:
    """Aggregate current live V2 producer throughput, or use starter output."""
    rows = (await session.execute(
        select(NatBusiness, NatCompany).join(
            NatCompany, NatCompany.id == NatBusiness.company_id
        ).where(
            NatBusiness.specialization == industry,
            NatBusiness.status.notin_(PAUSED_STATUSES),
            NatCompany.is_bankrupt.is_(False),
        ).order_by(NatBusiness.id)
    )).all()
    aggregate = 0.0
    for business, company in rows:
        spec = CAREER_BUSINESSES.get(business.business_type)
        if not spec or spec.get("legacy_hidden") or item_id not in spec.get("outputs_per_hour", {}):
            continue
        rates = resource_business_rates(
            business, spec, upgrading=business.status == "UPGRADING",
            output_bonus_multiplier=IndustryUpgradeService.bonus_multiplier(
                company, industry
            ),
        )
        aggregate += max(0.0, float(spec["outputs_per_hour"][item_id])) * rates.output_multiplier
    if aggregate > 0:
        return aggregate
    return max(0.0, float(starter.get("outputs_per_hour", {}).get(item_id, 0.0)))


__all__ = ["active_city_order_industries", "primary_output", "sector_output_rate"]
