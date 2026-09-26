"""Compute per-company resource storage capacity for lazy V2 settlement."""

from collections import defaultdict
from copy import copy
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.industry_upgrade_service import IndustryUpgradeService


class InventoryCapacityService:
    """Derive storage capacity from eligible company production and offline horizon.

    This service is intentionally calculation-only. It does not persist capacities
    or change the inventory settlement policy by itself.
    """

    PRODUCTION_STATUSES = frozenset({
        "ACTIVE", "UPGRADING", "PAUSED_SUPPLY", "PAUSED_STORAGE",
    })

    @classmethod
    def capacity_by_item(
        cls,
        company: NatCompany,
        businesses: Iterable[NatBusiness],
    ) -> dict[str, float]:
        """Return a minimum stock allowance plus one offline horizon of output.

        Throughput uses the same server rate function as lazy settlement, so
        stage, health, efficiency, asset multipliers, upgrade downtime, and the
        company's specialization-specific industry bonus are reflected.
        """
        if company.id is None or bool(company.is_bankrupt):
            return {}

        offline_hours = float(IdleEconomyService.offline_cap_hours(company))
        minimum_capacity = max(
            0.0, float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
        )
        throughput_by_item: dict[str, float] = defaultdict(float)

        for business in businesses:
            status = str(business.status or "").upper()
            if business.company_id != company.id or status not in cls.PRODUCTION_STATUSES:
                continue

            spec = get_business_spec(business.business_type)
            if (
                not spec
                or spec.get("legacy_hidden")
                or spec.get("mechanic") != "resource_production"
            ):
                continue

            bonus = IndustryUpgradeService.bonus_multiplier(
                company, business.specialization
            )
            rates = resource_business_rates(
                business,
                spec,
                upgrading=status == "UPGRADING",
                output_bonus_multiplier=bonus,
            )
            next_stage_rates = None
            if status == "UPGRADING" and int(business.stage or 1) < int(spec["max_stage"]):
                next_stage = copy(business)
                next_stage.stage = int(business.stage or 1) + 1
                next_stage_rates = resource_business_rates(
                    next_stage, spec, upgrading=False, output_bonus_multiplier=bonus
                )
            for item_id, base_rate in spec.get("outputs_per_hour", {}).items():
                hourly_output = float(base_rate) * rates.output_multiplier
                if next_stage_rates is not None:
                    hourly_output = max(
                        hourly_output,
                        float(base_rate) * next_stage_rates.output_multiplier,
                    )
                if hourly_output > 0:
                    throughput_by_item[item_id] += hourly_output

        capacities: dict[str, float] = {}
        for item_id, hourly_output in throughput_by_item.items():
            projected = hourly_output * offline_hours
            # Keep the established base allowance available as a buffer for
            # already-owned/traded inventory, then add one full offline window.
            capacities[item_id] = minimum_capacity + projected
        return capacities

    @classmethod
    async def for_company(
        cls,
        session: AsyncSession,
        company: NatCompany,
        *,
        businesses: Iterable[NatBusiness] | None = None,
    ) -> dict[str, float]:
        if businesses is None:
            businesses = (await session.execute(
                select(NatBusiness).where(NatBusiness.company_id == company.id)
            )).scalars().all()
        return cls.capacity_by_item(company, businesses)

    @classmethod
    async def for_item(
        cls,
        session: AsyncSession,
        company: NatCompany,
        item_id: str,
        *,
        businesses: Iterable[NatBusiness] | None = None,
    ) -> float:
        capacities = await cls.for_company(session, company, businesses=businesses)
        return float(capacities.get(item_id, nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM))


__all__ = ["InventoryCapacityService"]
