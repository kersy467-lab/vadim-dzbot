"""Transactional lazy settlement for NATBIRZHA 2.0 idle businesses."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, nat_settings, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, get_npc_buy_price
from backend.natbirzha.services.business_rates import cash_business_rates, resource_business_rates


class IdleEconomyService:
    """Settles V2 business state on demand; no global income cron is required."""

    @staticmethod
    def _finish_due_upgrade(business: NatBusiness, spec: dict[str, Any]) -> bool:
        if business.status != "UPGRADING" or business.upgrade_target_stage is None:
            return False
        business.stage = min(max(1, int(business.upgrade_target_stage)), int(spec["max_stage"]))
        metadata = dict(business.metadata_json or {})
        resume_status = metadata.pop("upgrade_resume_status", "ACTIVE")
        resumable_statuses = {
            "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY",
            "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
        }
        business.status = resume_status if resume_status in resumable_statuses else "ACTIVE"
        business.metadata_json = metadata
        business.upgrade_started_at = None
        business.upgrade_ready_at = None
        business.upgrade_target_stage = None
        return True

    @staticmethod
    def offline_cap_hours(company: NatCompany) -> int:
        """Offline horizon grows with company maturity, capped at one week."""
        base = max(1, int(nat_settings.TYCOON_V2_OFFLINE_CASH_CAP_HOURS))
        level = max(1, int(company.level or 1))
        if level >= 60:
            return max(base, 168)
        if level >= 40:
            return max(base, 72)
        if level >= 20:
            return max(base, 48)
        return base

    @staticmethod
    def _accrue_work_xp(business: NatBusiness, worked_hours: float) -> int:
        """Award production XP without losing fractions on frequent refreshes."""
        metadata = dict(business.metadata_json or {})
        pending = max(0.0, float(metadata.get("work_xp_fraction", 0.0) or 0.0))
        xp_per_hour = max(1, int(nat_settings.TYCOON_V2_WORK_XP_PER_HOUR))
        total = pending + max(0.0, float(worked_hours)) * xp_per_hour
        whole = int(total + 1e-9)
        metadata["work_xp_fraction"] = round(max(0.0, total - whole), 6)
        business.metadata_json = metadata
        return whole

    @classmethod
    def _settle_cash_segment(
        cls, business: NatBusiness, spec: dict[str, Any], *, hours: float, upgrading: bool,
        industry_bonus_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        if hours <= 0 or business.status in {"PAUSED_MANUAL", "PAUSED_SUPPLY", "PAUSED_MAINTENANCE", "PAUSED_STORAGE", "BANKRUPT", "MERGING"}:
            return 0.0, 0.0
        rates = cash_business_rates(
            business, spec, upgrading=upgrading,
            output_bonus_multiplier=industry_bonus_multiplier,
        )
        return rates.gross_per_hour * hours, rates.maintenance_per_hour * hours

    @classmethod
    def _settle_business(
        cls, business: NatBusiness, *, now: datetime, cap_hours: int,
        industry_bonus_multiplier: float = 1.0,
    ) -> dict[str, Any]:
        spec = get_business_spec(business.business_type)
        if spec is None:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "worked_hours": 0.0, "upgrade_completed": False}

        last_settled = normalize_dt(business.last_settled_at)
        if last_settled is None or now <= last_settled:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "worked_hours": 0.0, "upgrade_completed": False}

        max_end = last_settled + timedelta(hours=max(1, int(cap_hours)))
        settle_until = min(now, max_end)
        skipped_hours = max(0.0, (now - settle_until).total_seconds() / 3600)
        if settle_until <= last_settled:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "worked_hours": 0.0, "upgrade_completed": False}
        if business.status in {"PAUSED_MANUAL", "PAUSED_SUPPLY", "PAUSED_MAINTENANCE", "PAUSED_STORAGE", "BANKRUPT", "MERGING"}:
            # Advance the cursor while stopped: resuming must never back-pay an
            # intentionally paused interval.
            business.last_settled_at = now if skipped_hours > 0 else settle_until
            return {
                "gross": 0.0,
                "maintenance": 0.0,
                "hours": (settle_until - last_settled).total_seconds() / 3600,
                "worked_hours": 0.0,
                "upgrade_completed": False,
                "skipped_hours": skipped_hours,
            }

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
                business, spec, hours=first_hours, upgrading=True,
                industry_bonus_multiplier=industry_bonus_multiplier,
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
            industry_bonus_multiplier=industry_bonus_multiplier,
        )
        gross += segment_gross
        maintenance += segment_maintenance
        if skipped_hours > 0:
            late_ready = normalize_dt(business.upgrade_ready_at)
            if business.status == "UPGRADING" and late_ready is not None and late_ready <= now:
                upgrade_completed = cls._finish_due_upgrade(business, spec) or upgrade_completed
        business.last_settled_at = now if skipped_hours > 0 else settle_until
        return {
            "gross": gross,
            "maintenance": maintenance,
            "hours": (settle_until - last_settled).total_seconds() / 3600,
            "worked_hours": (settle_until - last_settled).total_seconds() / 3600,
            "upgrade_completed": upgrade_completed,
            "skipped_hours": skipped_hours,
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

    @staticmethod
    def _sale_mode(business: NatBusiness) -> str:
        mode = str((business.metadata_json or {}).get("sale_mode", "NPC")).upper()
        return mode if mode in {"NPC", "HOLD"} else "NPC"

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
        industry_bonus_multiplier: float = 1.0,
    ) -> tuple[float, float, float, float, list[str]]:
        """Consume inputs and return revenue, maintenance, worked hours and input cost basis."""
        if hours <= 0 or business.status in {
            "PAUSED_MANUAL", "PAUSED_MAINTENANCE", "BANKRUPT", "MERGING"
        }:
            return 0.0, 0.0, 0.0, 0.0, []
        rates = resource_business_rates(
            business, spec, upgrading=upgrading,
            output_bonus_multiplier=industry_bonus_multiplier,
        )
        if rates.output_multiplier <= 0:
            return 0.0, 0.0, 0.0, 0.0, []

        inputs = {
            item_id: float(rate) * rates.input_multiplier
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

        sale_mode = cls._sale_mode(business)
        output_rows: dict[str, NatInventory] = {}
        if sale_mode == "HOLD":
            cap = float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
            for item_id, base_rate in spec["outputs_per_hour"].items():
                rate = float(base_rate) * rates.output_multiplier
                if rate <= 0:
                    continue
                output = await cls._locked_inventory(session, company_id, item_id, create=True)
                output_rows[item_id] = output
                free = max(0.0, cap - float(output.quantity))
                actual_hours = min(actual_hours, free / rate)

        actual_hours = max(0.0, actual_hours)
        resource_cost = 0.0
        for item_id, rate in inputs.items():
            inventory = inventories[item_id]
            if inventory is not None:
                consumed = rate * actual_hours
                resource_cost += consumed * max(0.0, float(inventory.avg_cost_basis or 0.0))
                inventory.quantity = round(
                    max(0.0, float(inventory.quantity) - consumed), 6
                )

        revenue = 0.0
        for item_id, base_rate in spec["outputs_per_hour"].items():
            produced = float(base_rate) * rates.output_multiplier * actual_hours
            if produced <= 0:
                continue
            if sale_mode == "NPC":
                revenue += produced * get_npc_buy_price(item_id)
            else:
                output = output_rows[item_id]
                output.quantity = round(float(output.quantity) + produced, 6)

        maintenance = rates.maintenance_per_hour * actual_hours
        if actual_hours + 1e-9 < hours and not upgrading:
            business.status = "PAUSED_SUPPLY" if missing else "PAUSED_STORAGE"
        return (
            round(revenue, 6), round(maintenance, 6), actual_hours,
            round(resource_cost, 6), missing,
        )

    @classmethod
    async def _settle_resource_business(
        cls, session: AsyncSession, business: NatBusiness, spec: dict[str, Any], *, now: datetime,
        cap_hours: int, industry_bonus_multiplier: float = 1.0,
    ) -> dict[str, Any]:
        last_settled = normalize_dt(business.last_settled_at)
        if last_settled is None or now <= last_settled:
            return {"gross": 0.0, "maintenance": 0.0, "hours": 0.0, "worked_hours": 0.0, "upgrade_completed": False}
        settle_until = min(now, last_settled + timedelta(hours=max(1, int(cap_hours))))
        skipped_hours = max(0.0, (now - settle_until).total_seconds() / 3600)
        if business.status in {"PAUSED_SUPPLY", "PAUSED_STORAGE"}:
            business.status = "ACTIVE"

        gross = 0.0
        maintenance = 0.0
        resource_cost = 0.0
        worked_hours = 0.0
        cursor = last_settled
        completed = False
        ready_at = normalize_dt(business.upgrade_ready_at)
        if business.status == "UPGRADING" and ready_at is not None and ready_at <= cursor:
            completed = cls._finish_due_upgrade(business, spec)
            ready_at = None
        if business.status == "UPGRADING" and ready_at is not None and cursor < ready_at < settle_until:
            earned, paid, worked, inputs_cost, _ = await cls._settle_resource_segment(
                session, business.company_id, business, spec,
                hours=(ready_at - cursor).total_seconds() / 3600, upgrading=True,
                industry_bonus_multiplier=industry_bonus_multiplier,
            )
            gross += earned
            maintenance += paid
            resource_cost += inputs_cost
            worked_hours += worked
            cursor = ready_at
            completed = cls._finish_due_upgrade(business, spec)
        earned, paid, worked, inputs_cost, _ = await cls._settle_resource_segment(
            session, business.company_id, business, spec,
            hours=(settle_until - cursor).total_seconds() / 3600,
            upgrading=business.status == "UPGRADING",
            industry_bonus_multiplier=industry_bonus_multiplier,
        )
        gross += earned
        maintenance += paid
        resource_cost += inputs_cost
        worked_hours += worked
        if skipped_hours > 0:
            late_ready = normalize_dt(business.upgrade_ready_at)
            if business.status == "UPGRADING" and late_ready is not None and late_ready <= now:
                completed = cls._finish_due_upgrade(business, spec) or completed
        business.last_settled_at = now if skipped_hours > 0 else settle_until
        return {
            "gross": gross,
            "maintenance": maintenance,
            "hours": (settle_until - last_settled).total_seconds() / 3600,
            "worked_hours": worked_hours,
            "resource_cost": round(resource_cost, 6),
            "upgrade_completed": completed,
            "skipped_hours": skipped_hours,
        }

    @classmethod
    async def settle_company(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        """Apply lazy enterprise settlement and mandatory-tax blocking atomically."""
        from backend.natbirzha.services.idle_company_settlement import settle_company

        current = normalize_dt(now or get_game_now())
        return await settle_company(cls, session, company_id, current=current)



__all__ = ["IdleEconomyService"]
