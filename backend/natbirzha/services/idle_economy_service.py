"""Transactional lazy settlement for NATBIRZHA 2.0 idle businesses."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, nat_settings, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.business_rates import cash_business_rates, resource_business_multiplier
from backend.natbirzha.services.supply_policy_service import SupplyPolicyService


class IdleEconomyService:
    """Settles V2 business state on demand; no global income cron is required."""

    @staticmethod
    def _finish_due_upgrade(business: NatBusiness, spec: dict[str, Any]) -> bool:
        if business.status != "UPGRADING" or business.upgrade_target_stage is None:
            return False
        business.stage = min(max(1, int(business.upgrade_target_stage)), int(spec["max_stage"]))
        business.status = "ACTIVE"
        business.upgrade_started_at = None
        business.upgrade_ready_at = None
        business.upgrade_target_stage = None
        return True

    @classmethod
    def _settle_cash_segment(
        cls, business: NatBusiness, spec: dict[str, Any], *, hours: float, upgrading: bool
    ) -> tuple[float, float]:
        if hours <= 0 or business.status in {"PAUSED_MANUAL", "PAUSED_SUPPLY", "PAUSED_MAINTENANCE", "BANKRUPT", "MERGING"}:
            return 0.0, 0.0
        rates = cash_business_rates(business, spec, upgrading=upgrading)
        return rates.gross_per_hour * hours, rates.maintenance_per_hour * hours

    @classmethod
    def _settle_business(
        cls, business: NatBusiness, *, now: datetime
    ) -> dict[str, Any]:
        spec = get_business_spec(business.business_type)
        if spec is None:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "upgrade_completed": False}

        last_settled = normalize_dt(business.last_settled_at)
        if last_settled is None or now <= last_settled:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "upgrade_completed": False}

        max_end = last_settled + timedelta(hours=int(nat_settings.TYCOON_V2_OFFLINE_CASH_CAP_HOURS))
        settle_until = min(now, max_end)
        if settle_until <= last_settled:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "upgrade_completed": False}

        gross = 0.0
        maintenance = 0.0
        cursor = last_settled
        upgrade_completed = False
        ready_at = normalize_dt(business.upgrade_ready_at)

        if business.status == "UPGRADING" and ready_at is not None and ready_at <= cursor:
            upgrade_completed = cls._finish_due_upgrade(business, spec)
            ready_at = None

        if business.status == "UPGRADING" and ready_at is not None and cursor < ready_at < settle_until:
            first_hours = (ready_at - cursor).total_seconds() / 3600
            first_gross, first_maintenance = cls._settle_cash_segment(
                business, spec, hours=first_hours, upgrading=True
            )
            gross += first_gross
            maintenance += first_maintenance
            cursor = ready_at
            upgrade_completed = cls._finish_due_upgrade(business, spec)

        remaining_hours = (settle_until - cursor).total_seconds() / 3600
        segment_gross, segment_maintenance = cls._settle_cash_segment(
            business,
            spec,
            hours=remaining_hours,
            upgrading=business.status == "UPGRADING",
        )
        gross += segment_gross
        maintenance += segment_maintenance
        business.last_settled_at = settle_until
        return {
            "gross": gross,
            "maintenance": maintenance,
            "hours": (settle_until - last_settled).total_seconds() / 3600,
            "upgrade_completed": upgrade_completed,
        }

    @staticmethod
    async def _locked_inventory(
        session: AsyncSession, company_id: int, item_id: str, *, create: bool = False
    ) -> NatInventory | None:
        inventory = await session.scalar(
            select(NatInventory)
            .where(NatInventory.company_id == company_id, NatInventory.item_id == item_id)
            .with_for_update()
        )
        if inventory is None and create:
            inventory = NatInventory(company_id=company_id, item_id=item_id, quantity=0.0)
            session.add(inventory)
            await session.flush()
        return inventory

    @classmethod
    async def _settle_resource_segment(
        cls,
        session: AsyncSession,
        company_id: int,
        business: NatBusiness,
        spec: dict[str, Any],
        *,
        hours: float,
        upgrading: bool,
    ) -> tuple[float, float, list[str]]:
        """Consume inputs and create outputs for one continuous resource interval."""
        if hours <= 0 or business.status in {"PAUSED_MANUAL", "PAUSED_MAINTENANCE", "BANKRUPT", "MERGING"}:
            return 0.0, 0.0, []
        multiplier = resource_business_multiplier(business, spec, upgrading=upgrading)
        if multiplier <= 0:
            return 0.0, 0.0, []
        inputs = {
            item_id: float(rate) * multiplier
            for item_id, rate in spec["inputs_per_hour"].items()
            if float(rate) > 0
        }
        actual_hours = hours
        missing: list[str] = []
        inventories: dict[str, NatInventory | None] = {}
        for item_id, rate in inputs.items():
            inventory = await cls._locked_inventory(session, company_id, item_id)
            inventories[item_id] = inventory
            available = float(inventory.available_quantity) if inventory else 0.0
            actual_hours = min(actual_hours, available / rate)
            if available + 1e-9 < rate * hours:
                missing.append(item_id)
        actual_hours = max(0.0, actual_hours)
        for item_id, rate in inputs.items():
            inventory = inventories[item_id]
            if inventory is not None:
                inventory.quantity = round(max(0.0, float(inventory.quantity) - rate * actual_hours), 6)
        for item_id, rate in spec["outputs_per_hour"].items():
            output = await cls._locked_inventory(session, company_id, item_id, create=True)
            output.quantity = round(float(output.quantity) + float(rate) * multiplier * actual_hours, 6)

        maintenance = float(business.base_maintenance_per_hour) * max(0.0, float(business.efficiency)) * actual_hours
        if actual_hours + 1e-9 < hours and not upgrading:
            business.status = "PAUSED_SUPPLY"
        return round(maintenance, 6), actual_hours, missing

    @classmethod
    async def _settle_resource_business(
        cls, session: AsyncSession, business: NatBusiness, spec: dict[str, Any], *, now: datetime
    ) -> dict[str, Any]:
        last_settled = normalize_dt(business.last_settled_at)
        if last_settled is None or now <= last_settled:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "upgrade_completed": False}
        settle_until = min(
            now, last_settled + timedelta(hours=int(nat_settings.TYCOON_V2_OFFLINE_CASH_CAP_HOURS))
        )
        if business.status == "PAUSED_SUPPLY":
            business.status = "ACTIVE"

        maintenance = 0.0
        cursor = last_settled
        completed = False
        ready_at = normalize_dt(business.upgrade_ready_at)
        if business.status == "UPGRADING" and ready_at is not None and ready_at <= cursor:
            completed = cls._finish_due_upgrade(business, spec)
            ready_at = None
        if business.status == "UPGRADING" and ready_at is not None and cursor < ready_at < settle_until:
            paid, _, _ = await cls._settle_resource_segment(
                session, business.company_id, business, spec,
                hours=(ready_at - cursor).total_seconds() / 3600, upgrading=True,
            )
            maintenance += paid
            cursor = ready_at
            completed = cls._finish_due_upgrade(business, spec)
        paid, _, _ = await cls._settle_resource_segment(
            session, business.company_id, business, spec,
            hours=(settle_until - cursor).total_seconds() / 3600,
            upgrading=business.status == "UPGRADING",
        )
        maintenance += paid
        business.last_settled_at = settle_until
        return {
            "gross": 0.0,
            "maintenance": maintenance,
            "hours": (settle_until - last_settled).total_seconds() / 3600,
            "upgrade_completed": completed,
        }

    @classmethod
    async def settle_company(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        """Apply due cash-only business income in the caller's transaction."""
        current = normalize_dt(now or get_game_now())
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Company not found")

        businesses = list((await session.execute(
            select(NatBusiness)
            .where(NatBusiness.company_id == company.id)
            .order_by(NatBusiness.id)
            .with_for_update()
        )).scalars().all())

        gross = 0.0
        maintenance = 0.0
        settled_hours = 0.0
        completed_upgrades: list[int] = []
        for business in businesses:
            spec = get_business_spec(business.business_type)
            if not spec:
                continue
            if spec["mechanic"] == "cash_income":
                result = cls._settle_business(business, now=current)
            elif spec["mechanic"] == "resource_production":
                await SupplyPolicyService.auto_procure(session, company, business, spec)
                result = await cls._settle_resource_business(session, business, spec, now=current)
            else:
                continue
            gross += result["gross"]
            maintenance += result["maintenance"]
            settled_hours = max(settled_hours, result["hours"])
            if result["upgrade_completed"]:
                completed_upgrades.append(business.id)

        net_cash = round(gross - maintenance, 2)
        if net_cash:
            company.cash = round(float(company.cash) + net_cash, 2)
        await session.flush()
        return {
            "company_id": company.id,
            "gross_cash": round(gross, 2),
            "maintenance_cash": round(maintenance, 2),
            "net_cash": net_cash,
            "settled_hours": round(settled_hours, 4),
            "completed_upgrades": completed_upgrades,
        }


__all__ = ["IdleEconomyService"]
