"""Server-authoritative opening and staged upgrading of idle businesses."""

from datetime import datetime, timedelta
from math import ceil
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.business_resource_service import consume_business_resources
from backend.natbirzha.services.business_capacity_service import BusinessCapacityService
from backend.natbirzha.services.progression_service import apply_xp


UPGRADE_TIME_CURVES: dict[str, tuple[int, int]] = {
    "starter": (3, 360),
    "industry": (12, 720),
    "service": (8, 480),
    "advanced": (30, 1_440),
    "career": (3, 1_440),
}


class BusinessService:
    @staticmethod
    def business_slot_limits(*, capacity: int, used: int) -> dict[str, int]:
        maximum = max(BusinessCapacityService.BASE_CAPACITY, min(BusinessCapacityService.MAX_CAPACITY, int(capacity)))
        return {"used": int(used), "max": maximum, "free": max(0, maximum - int(used))}

    @staticmethod
    def project_slot_limits(*, level: int, active: int) -> dict[str, int]:
        """Limit simultaneous milestone projects without throttling ordinary levels."""
        maximum = 1 + sum(1 for threshold in (12, 25, 40, 60) if int(level) >= threshold)
        return {"used": int(active), "max": maximum, "free": max(0, maximum - int(active))}

    @staticmethod
    def _is_milestone_upgrade(business: NatBusiness) -> bool:
        spec = get_business_spec(business.business_type)
        target = int(business.upgrade_target_stage or 0)
        return bool(spec and target in spec.get("milestones", {}))

    @classmethod
    async def _active_milestone_projects(cls, session: AsyncSession, company_id: int) -> int:
        rows = (await session.execute(
            select(NatBusiness).where(
                NatBusiness.company_id == company_id, NatBusiness.status == "UPGRADING"
            )
        )).scalars().all()
        return sum(1 for business in rows if cls._is_milestone_upgrade(business))

    @staticmethod
    def upgrade_quote(spec: dict[str, Any], stage: int) -> dict[str, Any]:
        current_stage = max(1, int(stage))
        target_stage = current_stage + 1
        base_multiplier = float(spec.get("upgrade_cost_base_multiplier", 0.25))
        base_cost = max(500.0, float(spec["open_cost"]) * base_multiplier)
        cost = base_cost * (float(spec["upgrade_cost_growth"]) ** (current_stage - 1))
        base_minutes, max_minutes = UPGRADE_TIME_CURVES[spec["upgrade_time_curve"]]
        minutes = min(max_minutes, max(1, ceil(base_minutes * (1.22 ** (current_stage - 1)))))
        milestone = spec.get("milestones", {}).get(target_stage)
        if milestone:
            cost *= float(milestone.get("cash_multiplier", 1.0))
            minutes = min(10_080, ceil(minutes * float(milestone.get("duration_multiplier", 1.0))))
        return {
            "cost": round(cost, 2),
            "duration_minutes": int(minutes),
            "target_stage": target_stage,
            "milestone": {"stage": target_stage, **milestone} if milestone else None,
        }

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
            raise ValueError("Компания не найдена")
        return company

    @staticmethod
    async def _used_slots(session: AsyncSession, company_id: int) -> int:
        rows = (await session.execute(
            select(NatBusiness).where(
                NatBusiness.company_id == company_id, NatBusiness.status != "BANKRUPT"
            )
        )).scalars().all()
        return sum(
            int(row.slot_weight) for row in rows
            if not (get_business_spec(row.business_type) or {}).get("legacy_hidden", False)
        )

    @staticmethod
    async def _company_businesses(session: AsyncSession, company_id: int) -> dict[str, list[NatBusiness]]:
        rows = (await session.execute(
            select(NatBusiness)
            .where(NatBusiness.company_id == company_id, NatBusiness.status != "BANKRUPT")
            .with_for_update()
        )).scalars().all()
        businesses: dict[str, list[NatBusiness]] = {}
        for row in rows:
            if (get_business_spec(row.business_type) or {}).get("legacy_hidden", False):
                continue
            businesses.setdefault(row.business_type, []).append(row)
        return businesses

    @staticmethod
    async def _consume_resources(
        session: AsyncSession, company_id: int, requirements: dict[str, float]
    ) -> None:
        await consume_business_resources(session, company_id, requirements)

    @staticmethod
    def _validate_open_requirements(
        company: NatCompany,
        spec: dict[str, Any],
        existing: dict[str, list[NatBusiness]],
    ) -> None:
        if spec.get("legacy_hidden"):
            raise ValueError("Это предприятие относится к старой версии экономики")
        if spec.get("unique", True) and existing.get(spec["id"]):
            raise ValueError("Это предприятие уже принадлежит вашей компании")
        if spec["specialization"] != company.specialization:
            if company.level < 30 or company.licensed_foreign_spec != spec["specialization"]:
                raise ValueError("Предприятие недоступно для основной отрасли компании")
        if int(company.level) < int(spec.get("company_level_required", 1)):
            raise ValueError(f"Требуется уровень компании {spec['company_level_required']}")
        if int(company.territory_tiles) < int(spec.get("territory_required", 0)):
            raise ValueError(f"Требуется территория: {spec['territory_required']} ед.")
        for business_type, stage in spec.get("prerequisites", {}).items():
            owned = existing.get(business_type, [])
            highest_stage = max((int(item.stage) for item in owned), default=0)
            if highest_stage < int(stage):
                prereq = get_business_spec(business_type)
                name = prereq["name"] if prereq else business_type
                raise ValueError(f"Сначала развейте «{name}» до уровня {stage}")

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
            raise ValueError("Неизвестный тип предприятия")
        current = normalize_dt(now or get_game_now())
        await IdleEconomyService.settle_company(session, company_id, now=current)
        company = await cls._locked_company(session, company_id)
        existing = await cls._company_businesses(session, company.id)
        cls._validate_open_requirements(company, spec, existing)

        used_slots = await cls._used_slots(session, company.id)
        slots = BusinessCapacityService.slot_limits(company, used=used_slots, now=current)
        if used_slots + int(spec["slot_weight"]) > slots["max"]:
            raise ValueError("Нет свободной корпоративной мощности для нового предприятия")
        open_cost = round(float(spec["open_cost"]), 2)
        if float(company.cash) < open_cost:
            raise ValueError("Недостаточно cash для открытия предприятия")

        await cls._consume_resources(session, company.id, spec.get("open_resources", {}))
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
            metadata_json={"sale_mode": "NPC"},
        )
        session.add(business)
        await session.flush()
        progression = apply_xp(
            company, 75 + int(spec.get("industry_order", 1)) * 25
        )
        return {
            "success": True,
            "open_cost": open_cost,
            "remaining_cash": company.cash,
            "progression": progression,
            "business": cls._serialize_business(business),
            "slots": cls.business_slot_limits(
                capacity=BusinessCapacityService.effective_capacity(company, now=current),
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
        _skip_settlement: bool = False,
    ) -> dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        if not _skip_settlement:
            await IdleEconomyService.settle_company(session, company_id, now=current)
        company = await cls._locked_company(session, company_id)
        business = await session.scalar(
            select(NatBusiness).where(
                NatBusiness.id == business_id, NatBusiness.company_id == company.id
            ).with_for_update()
        )
        if business is None:
            raise ValueError("Предприятие не найдено")
        spec = get_business_spec(business.business_type)
        if spec is None:
            raise ValueError("Предприятие отсутствует в игровом каталоге")
        contract_license = (business.metadata_json or {}).get("contract_license")
        if contract_license:
            from backend.natbirzha.services.premium_service import PremiumService

            await PremiumService.require_active_license(
                session, company.id, str(contract_license)
            )
        if business.status == "UPGRADING":
            raise ValueError("Улучшение уже выполняется")
        resumable_statuses = {
            "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY",
            "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
        }
        if business.status not in resumable_statuses:
            raise ValueError("Предприятие нельзя улучшить в текущем состоянии")
        if business.stage >= int(spec["max_stage"]):
            raise ValueError("Достигнут максимальный уровень предприятия")

        quote = cls.upgrade_quote(spec, business.stage)
        if quote.get("milestone"):
            active_projects = await cls._active_milestone_projects(session, company.id)
            project_slots = cls.project_slot_limits(level=company.level, active=active_projects)
            if project_slots["free"] <= 0:
                raise ValueError(
                    f"Все проектные мощности заняты ({project_slots['used']}/{project_slots['max']})"
                )
        if float(company.cash) < quote["cost"]:
            raise ValueError("Недостаточно cash для улучшения")
        milestone = quote.get("milestone") or {}
        await cls._consume_resources(session, company.id, milestone.get("resources", {}))
        company.cash = round(float(company.cash) - quote["cost"], 2)
        metadata = dict(business.metadata_json or {})
        metadata["upgrade_resume_status"] = business.status
        business.metadata_json = metadata
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
            "milestone": quote.get("milestone"),
            "ready_at": business.upgrade_ready_at,
            "remaining_cash": company.cash,
        }

    @classmethod
    async def configure_sale_mode(
        cls,
        session: AsyncSession,
        company_id: int,
        business_id: int,
        mode: str,
    ) -> dict[str, Any]:
        normalized = (mode or "").strip().upper()
        if normalized not in {"NPC", "HOLD"}:
            raise ValueError("Режим продажи должен быть NPC или HOLD")
        business = await session.scalar(
            select(NatBusiness).where(
                NatBusiness.id == business_id, NatBusiness.company_id == company_id
            ).with_for_update()
        )
        if business is None:
            raise ValueError("Предприятие не найдено")
        spec = get_business_spec(business.business_type)
        if spec is None or spec["mechanic"] != "resource_production":
            raise ValueError("Для этого предприятия режим реализации не используется")
        metadata = dict(business.metadata_json or {})
        metadata["sale_mode"] = normalized
        business.metadata_json = metadata
        if business.status == "PAUSED_STORAGE" and normalized == "NPC":
            business.status = "ACTIVE"
        await session.flush()
        return {"success": True, "business_id": business.id, "sale_mode": normalized}

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
            raise ValueError("Предприятие не найдено")
        return business

    @classmethod
    async def pause(
        cls, session: AsyncSession, company_id: int, business_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        business = await cls._lifecycle_business(session, company_id, business_id, now=now)
        if business.status == "UPGRADING":
            raise ValueError("Нельзя поставить предприятие на паузу во время улучшения")
        if business.status in {"BANKRUPT", "MERGING"}:
            raise ValueError("Предприятие нельзя поставить на паузу в текущем состоянии")
        business.status = "PAUSED_MANUAL"
        await session.flush()
        return {"success": True, "business_id": business.id, "status": business.status}

    @classmethod
    async def resume(
        cls, session: AsyncSession, company_id: int, business_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        business = await cls._lifecycle_business(session, company_id, business_id, now=now)
        if business.status != "PAUSED_MANUAL":
            raise ValueError("Возобновить можно только предприятие на ручной паузе")
        if (business.metadata_json or {}).get("contract_expired"):
            raise ValueError("Контракт на предприятие истёк. Продлите его в разделе PVC")
        business.status = "ACTIVE"
        await session.flush()
        return {"success": True, "business_id": business.id, "status": business.status}

    @classmethod
    async def sell(
        cls, session: AsyncSession, company_id: int, business_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        business = await cls._lifecycle_business(session, company_id, business_id, now=now)
        if (business.metadata_json or {}).get("contract_license"):
            raise ValueError("Контрактное предприятие нельзя продать: улучшения сохраняются при продлении")
        if business.status == "UPGRADING":
            raise ValueError("Нельзя продать предприятие во время улучшения")
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
