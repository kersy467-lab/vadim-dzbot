"""Server-authoritative opening and staged upgrading of V2 businesses."""

from datetime import datetime, timedelta
from math import ceil
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


UPGRADE_TIME_CURVES: dict[str, tuple[int, int]] = {
    "starter": (3, 360),
    "industry": (12, 720),
    "service": (8, 480),
    "advanced": (30, 1_440),
}


class BusinessService:
    @staticmethod
    def business_slot_limits(*, level: int, territory_tiles: int, used: int) -> dict[str, int]:
        level_slots = sum(1 for threshold in (6, 12, 20, 30, 45, 60) if int(level) >= threshold)
        territory_slots = min(4, max(0, int(territory_tiles) // 5))
        maximum = min(16, 3 + level_slots + territory_slots)
        return {"used": int(used), "max": maximum, "free": max(0, maximum - int(used))}

    @staticmethod
    def upgrade_quote(spec: dict[str, Any], stage: int) -> dict[str, Any]:
        current_stage = max(1, int(stage))
        base_cost = max(500.0, float(spec["open_cost"]) * 0.25)
        cost = round(base_cost * (float(spec["upgrade_cost_growth"]) ** (current_stage - 1)), 2)
        base_minutes, max_minutes = UPGRADE_TIME_CURVES[spec["upgrade_time_curve"]]
        minutes = min(max_minutes, max(1, ceil(base_minutes * (1.22 ** (current_stage - 1)))))
        return {"cost": cost, "duration_minutes": minutes, "target_stage": current_stage + 1}

    @staticmethod
    def _serialize_business(business: NatBusiness) -> dict[str, Any]:
        return {
            "id": business.id,
            "business_type": business.business_type,
            "name": business.custom_name,
            "stage": business.stage,
            "status": business.status,
            "slot_weight": business.slot_weight,
            "last_settled_at": business.last_settled_at,
            "upgrade_ready_at": business.upgrade_ready_at,
        }

    @staticmethod
    async def _locked_company(session: AsyncSession, company_id: int) -> NatCompany:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Company not found")
        return company

    @staticmethod
    async def _used_slots(session: AsyncSession, company_id: int) -> int:
        value = await session.scalar(
            select(func.coalesce(func.sum(NatBusiness.slot_weight), 0)).where(
                NatBusiness.company_id == company_id,
                NatBusiness.status != "BANKRUPT",
            )
        )
        return int(value or 0)

    @classmethod
    async def open_business(
        cls,
        session: AsyncSession,
        company_id: int,
        business_type: str,
        *,
        custom_name: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        spec = get_business_spec(business_type)
        if spec is None:
            raise ValueError("Unknown business type")
        current = normalize_dt(now or get_game_now())
        await IdleEconomyService.settle_company(session, company_id, now=current)
        company = await cls._locked_company(session, company_id)
        used_slots = await cls._used_slots(session, company.id)
        current_slots = cls.business_slot_limits(
            level=company.level, territory_tiles=company.territory_tiles, used=used_slots
        )
        if used_slots + int(spec["slot_weight"]) > current_slots["max"]:
            raise ValueError("No free business slots")
        open_cost = round(float(spec["open_cost"]), 2)
        if float(company.cash) < open_cost:
            raise ValueError("Insufficient cash to open business")

        company.cash = round(float(company.cash) - open_cost, 2)
        business = NatBusiness(
            company_id=company.id,
            business_type=spec["id"],
            custom_name=(custom_name or spec["name"]).strip()[:120] or spec["name"],
            specialization=spec["specialization"],
            stage=1,
            status="ACTIVE",
            capital_invested=open_cost,
            base_income_per_hour=float(spec["base_income_per_hour"]),
            base_maintenance_per_hour=float(spec["base_maintenance_per_hour"]),
            last_settled_at=current,
            slot_weight=int(spec["slot_weight"]),
        )
        session.add(business)
        await session.flush()
        return {
            "success": True,
            "open_cost": open_cost,
            "remaining_cash": company.cash,
            "business": cls._serialize_business(business),
            "slots": cls.business_slot_limits(
                level=company.level, territory_tiles=company.territory_tiles,
                used=used_slots + int(spec["slot_weight"]),
            ),
        }

    @classmethod
    async def start_upgrade(
        cls,
        session: AsyncSession,
        company_id: int,
        business_id: int,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        await IdleEconomyService.settle_company(session, company_id, now=current)
        company = await cls._locked_company(session, company_id)
        business = await session.scalar(
            select(NatBusiness).where(
                NatBusiness.id == business_id, NatBusiness.company_id == company.id
            ).with_for_update()
        )
        if business is None:
            raise ValueError("Business not found")
        spec = get_business_spec(business.business_type)
        if spec is None:
            raise ValueError("Business catalog entry is missing")
        if business.status == "UPGRADING":
            raise ValueError("Business upgrade is already in progress")
        if business.status != "ACTIVE":
            raise ValueError("Business must be active before upgrading")
        if business.stage >= int(spec["max_stage"]):
            raise ValueError("Business is already at maximum stage")

        quote = cls.upgrade_quote(spec, business.stage)
        if float(company.cash) < quote["cost"]:
            raise ValueError("Insufficient cash to upgrade business")
        company.cash = round(float(company.cash) - quote["cost"], 2)
        business.status = "UPGRADING"
        business.upgrade_started_at = current
        business.upgrade_ready_at = current + timedelta(minutes=quote["duration_minutes"])
        business.upgrade_target_stage = quote["target_stage"]
        business.capital_invested = round(float(business.capital_invested) + quote["cost"], 2)
        await session.flush()
        return {
            "success": True,
            "business_id": business.id,
            "cost": quote["cost"],
            "target_stage": quote["target_stage"],
            "duration_minutes": quote["duration_minutes"],
            "ready_at": business.upgrade_ready_at,
            "remaining_cash": company.cash,
        }

    @classmethod
    async def _lifecycle_business(
        cls, session: AsyncSession, company_id: int, business_id: int, *, now: datetime | None
    ) -> NatBusiness:
        current = normalize_dt(now or get_game_now())
        await IdleEconomyService.settle_company(session, company_id, now=current)
        business = await session.scalar(
            select(NatBusiness).where(
                NatBusiness.id == business_id, NatBusiness.company_id == company_id
            ).with_for_update()
        )
        if business is None:
            raise ValueError("Business not found")
        return business

    @classmethod
    async def pause(
        cls, session: AsyncSession, company_id: int, business_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        business = await cls._lifecycle_business(session, company_id, business_id, now=now)
        if business.status == "UPGRADING":
            raise ValueError("Cannot pause a business while its upgrade is in progress")
        if business.status in {"BANKRUPT", "MERGING"}:
            raise ValueError("Business cannot be paused in its current state")
        business.status = "PAUSED_MANUAL"
        await session.flush()
        return {"success": True, "business_id": business.id, "status": business.status}

    @classmethod
    async def resume(
        cls, session: AsyncSession, company_id: int, business_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        business = await cls._lifecycle_business(session, company_id, business_id, now=now)
        if business.status != "PAUSED_MANUAL":
            raise ValueError("Only manually paused businesses can be resumed")
        business.status = "ACTIVE"
        await session.flush()
        return {"success": True, "business_id": business.id, "status": business.status}

    @classmethod
    async def sell(
        cls, session: AsyncSession, company_id: int, business_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        business = await cls._lifecycle_business(session, company_id, business_id, now=now)
        if business.status == "UPGRADING":
            raise ValueError("Cannot sell a business while its upgrade is in progress")
        company = await cls._locked_company(session, company_id)
        refund = round(max(0.0, float(business.capital_invested)) * 0.40, 2)
        company.cash = round(float(company.cash) + refund, 2)
        await session.delete(business)
        await session.flush()
        return {
            "success": True,
            "business_id": business_id,
            "refund": refund,
            "remaining_cash": company.cash,
        }


__all__ = ["BusinessService", "UPGRADE_TIME_CURVES"]
