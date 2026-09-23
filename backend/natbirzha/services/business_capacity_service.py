"""Paid, timed expansion of a company's available business slots."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.company import NatCompany


class BusinessCapacityService:
    BASE_CAPACITY = 10
    MAX_CAPACITY = 50
    BASE_COST = 100_000.0
    COST_GROWTH = 1.5
    MAX_EXPANSION_HOURS = 72

    @classmethod
    def effective_capacity(cls, company: NatCompany, *, now: datetime | None = None) -> int:
        current = max(cls.BASE_CAPACITY, min(cls.MAX_CAPACITY, int(company.business_slot_capacity or cls.BASE_CAPACITY)))
        ready_at = normalize_dt(company.business_slot_upgrade_ready_at)
        moment = normalize_dt(now or get_game_now())
        if ready_at and ready_at <= moment and current < cls.MAX_CAPACITY:
            return current + 1
        return current

    @classmethod
    def quote(cls, company: NatCompany, *, now: datetime | None = None) -> dict[str, Any]:
        moment = normalize_dt(now or get_game_now())
        capacity = cls.effective_capacity(company, now=moment)
        ready_at = normalize_dt(company.business_slot_upgrade_ready_at)
        pending = bool(ready_at and ready_at > moment)
        target = min(cls.MAX_CAPACITY, capacity + 1)
        expansion_number = max(1, target - cls.BASE_CAPACITY)
        return {
            "current_capacity": capacity,
            "target_capacity": target if capacity < cls.MAX_CAPACITY else None,
            "max_capacity": cls.MAX_CAPACITY,
            "cost": round(cls.BASE_COST * (cls.COST_GROWTH ** (expansion_number - 1)), 2)
                if capacity < cls.MAX_CAPACITY else None,
            "duration_hours": min(cls.MAX_EXPANSION_HOURS, 6 * expansion_number)
                if capacity < cls.MAX_CAPACITY else None,
            "is_upgrading": pending,
            "ready_at": ready_at.isoformat() if pending else None,
            "remaining_seconds": max(0, int((ready_at - moment).total_seconds())) if pending else 0,
            "maxed": capacity >= cls.MAX_CAPACITY,
        }

    @classmethod
    def slot_limits(cls, company: NatCompany, *, used: int, now: datetime | None = None) -> dict[str, int]:
        capacity = cls.effective_capacity(company, now=now)
        return {"used": int(used), "max": capacity, "free": max(0, capacity - int(used))}

    @classmethod
    async def _complete_due_expansion(cls, company: NatCompany, *, now: datetime) -> None:
        ready_at = normalize_dt(company.business_slot_upgrade_ready_at)
        if ready_at and ready_at <= now:
            company.business_slot_capacity = min(
                cls.MAX_CAPACITY,
                max(cls.BASE_CAPACITY, int(company.business_slot_capacity or cls.BASE_CAPACITY)) + 1,
            )
            company.business_slot_upgrade_ready_at = None

    @classmethod
    async def expand(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        moment = normalize_dt(now or get_game_now())
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Компания не найдена")
        await cls._complete_due_expansion(company, now=moment)
        quote = cls.quote(company, now=moment)
        if quote["maxed"]:
            raise ValueError("Достигнут предел корпоративной мощности")
        if quote["is_upgrading"]:
            raise ValueError("Расширение корпоративной мощности уже выполняется")
        if float(company.cash) < quote["cost"]:
            raise ValueError(f"Недостаточно cash: нужно {quote['cost']:,.0f}")

        company.cash = round(float(company.cash) - quote["cost"], 2)
        ready_at = moment + timedelta(hours=quote["duration_hours"])
        company.business_slot_upgrade_ready_at = ready_at
        await session.flush()
        return {
            "success": True,
            **quote,
            "is_upgrading": True,
            "ready_at": ready_at.isoformat(),
            "remaining_seconds": quote["duration_hours"] * 3600,
            "remaining_cash": company.cash,
        }


__all__ = ["BusinessCapacityService"]
