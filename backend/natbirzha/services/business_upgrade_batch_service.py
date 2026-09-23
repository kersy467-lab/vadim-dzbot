"""Atomic start of every currently affordable business upgrade."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


class BusinessUpgradeBatchService:
    RESUMABLE_STATUSES = {
        "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY",
        "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
    }

    @classmethod
    async def start_all(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict:
        moment = normalize_dt(now or get_game_now())
        await IdleEconomyService.settle_company(session, company_id, now=moment)
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Компания не найдена")

        businesses = list((await session.scalars(
            select(NatBusiness)
            .where(NatBusiness.company_id == company_id)
            .order_by(NatBusiness.id)
            .with_for_update()
        )).all())
        inventory_rows = list((await session.scalars(
            select(NatInventory)
            .where(NatInventory.company_id == company_id)
            .with_for_update()
        )).all())
        available_resources = {
            row.item_id: float(row.available_quantity) for row in inventory_rows
        }

        active_projects = await BusinessService._active_milestone_projects(session, company_id)
        project_slots = BusinessService.project_slot_limits(
            level=company.level, active=active_projects
        )["free"]
        candidates: list[tuple[NatBusiness, float]] = []
        for business in businesses:
            spec = get_business_spec(business.business_type)
            metadata = business.metadata_json or {}
            if (
                spec is None
                or spec.get("legacy_hidden")
                or business.status not in cls.RESUMABLE_STATUSES
                or metadata.get("contract_expired")
                or int(business.stage) >= int(spec["max_stage"])
            ):
                continue

            quote = BusinessService.upgrade_quote(spec, business.stage)
            milestone = quote.get("milestone") or {}
            resources = milestone.get("resources", {})
            if milestone:
                if project_slots <= 0:
                    continue
                if any(
                    available_resources.get(item_id, 0.0) + 1e-9 < float(quantity)
                    for item_id, quantity in resources.items()
                ):
                    continue
                for item_id, quantity in resources.items():
                    available_resources[item_id] = (
                        available_resources.get(item_id, 0.0) - float(quantity)
                    )
                project_slots -= 1
            candidates.append((business, float(quote["cost"])))

        total_cost = round(sum(cost for _, cost in candidates), 2)
        available_cash = round(float(company.cash), 2)
        if total_cost > available_cash + 1e-6:
            raise ValueError(
                "Недостаточно средств для прокачки всех доступных предприятий: "
                f"нужно {total_cost:,.0f} cash, доступно {available_cash:,.0f} cash"
            )

        upgrades = [
            await BusinessService.start_upgrade(
                session, company_id, business.id, now=moment, _skip_settlement=True
            )
            for business, _ in candidates
        ]
        await session.flush()
        return {
            "success": True,
            "started_count": len(upgrades),
            "total_cost": total_cost,
            "remaining_cash": round(float(company.cash), 2),
            "upgrades": upgrades,
        }


__all__ = ["BusinessUpgradeBatchService"]
