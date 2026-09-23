from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.building_catalog import (
    get_building_spec,
    list_catalog_for_company,
    resolve_building_type,
)
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.upgrade_service import UpgradeService
from backend.natbirzha.services.premium_service import PremiumService
from backend.natbirzha.services.mastery_service import MasteryService
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.building_economics import estimate_building_economics


class BuildingService:
    @staticmethod
    def get_catalog_for_company(
        company: Optional[NatCompany],
        *,
        existing_count: int = 0,
        active_licenses: Optional[set[str]] = None,
    ) -> List[Dict[str, Any]]:
        catalog = list_catalog_for_company(company)
        if company is None:
            return catalog

        slots = BuildingService.slot_limits(company, existing_count)
        industry_discount = MasteryService.effect(company, "industry")
        licensed = active_licenses or set()
        for item in catalog:
            base_cost = float(item["build_cost"])
            cost = max(1.0, round(base_cost * (1.0 - industry_discount), 2))
            is_own = item["specialization"] == company.specialization
            is_licensed_foreign = (
                not is_own
                and company.licensed_foreign_spec == item["specialization"]
            )
            efficiency = 1.0 if is_own else (0.12 if is_licensed_foreign else 0.10)
            has_required_license = (
                not item.get("required_license")
                or item["required_license"] in licensed
            )
            unlocked = int(company.level) >= int(item["level_required"])
            can_afford = float(company.cash) >= cost
            has_slot = slots["free"] > 0
            can_build = unlocked and can_afford and has_slot and has_required_license
            item.update({
                "base_build_cost": base_cost,
                "build_cost": cost,
                "is_own_specialization": is_own,
                "is_licensed_foreign": is_licensed_foreign,
                "efficiency": efficiency,
                "required_license_active": has_required_license,
                "can_afford": can_afford,
                "has_construction_slot": has_slot,
                "can_build": can_build,
                "status": (
                    "need_level" if not unlocked else
                    "need_license" if not has_required_license else
                    "no_slots" if not has_slot else
                    "need_cash" if not can_afford else
                    "available"
                ),
            })
            item["profitability"] = estimate_building_economics(
                item, efficiency=efficiency, build_cost=cost
            )
            item["profitability_basis"] = "npc_price_corridor"
            item["recommended_for_specialization"] = False
            item["recommendation_rank"] = None

        candidates = [
            item for item in catalog
            if item["specialization"] == company.specialization
            and item["profitability"]["payback_hours"] is not None
        ]
        candidates.sort(key=lambda item: (
            item["profitability"]["payback_hours"], item["id"]
        ))
        for rank, item in enumerate(candidates[:3], start=1):
            item["recommended_for_specialization"] = True
            item["recommendation_rank"] = rank
        return catalog

    @staticmethod
    def slot_limits(company: NatCompany, used: int = 0) -> Dict[str, int]:
        level_slots = max(3, 3 + (int(company.level) - 1))
        territory_slots = max(1, int(company.territory_tiles))
        maximum = min(level_slots, territory_slots)
        return {"used": int(used), "max": maximum, "free": max(0, maximum - int(used))}

    @staticmethod
    async def get_building_details(
        session: AsyncSession, company: NatCompany, factory_id: int
    ) -> Optional[Dict[str, Any]]:
        result = await session.execute(
            select(NatFactory).where(
                NatFactory.id == factory_id,
                NatFactory.company_id == company.id,
            )
        )
        factory = result.scalar_one_or_none()
        if not factory:
            return None

        spec = get_building_spec(factory.building_type) or {}
        now = normalize_dt(get_game_now())
        ready_at = normalize_dt(factory.cycle_ready_at)
        is_running = bool(ready_at and now < ready_at)
        is_ready = bool(ready_at and now >= ready_at)
        return {
            "id": factory.id,
            "building_type": factory.building_type,
            "name": spec.get("name", factory.building_type),
            "description": spec.get("description", ""),
            "specialization": factory.specialization,
            "category": spec.get("category", "processing"),
            "level_required": spec.get("level_required", 1),
            "build_cost": spec.get("build_cost", 0.0),
            "workers_required": spec.get("workers_required", factory.workers),
            "energy_required": spec.get("energy_required", 0),
            "cycle_duration": spec.get("cycle_duration", 60),
            "inputs": spec.get("inputs", {}),
            "outputs": spec.get("outputs", {}),
            "recipe_id": spec.get("recipe_id"),
            "current_recipe": factory.current_recipe,
            "efficiency": ProductionTickEngine.get_effective_efficiency(company, factory),
            "level": factory.level,
            "upgrade_level": factory.level,
            "automation_level": factory.automation_level,
            "technology_level": factory.technology_level,
            "workers": factory.workers,
            "status": "ready" if is_ready else ("running" if is_running else "idle"),
            "cycle_started_at": factory.cycle_started_at.isoformat() if factory.cycle_started_at else None,
            "cycle_ready_at": factory.cycle_ready_at.isoformat() if factory.cycle_ready_at else None,
            "upgrade_options": BuildingService.describe_upgrades(factory, company),
        }

    @staticmethod
    async def build_factory(
        session: AsyncSession,
        company: NatCompany,
        raw_type: str,
        idempotency_key: Optional[str] = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        del idempotency_key  # handled by API transaction layer
        locked_company = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        if not locked_company:
            raise ValueError("Company not found")
        company = locked_company

        building_type = resolve_building_type(raw_type)
        spec = get_building_spec(building_type)
        if not spec:
            raise ValueError(f"Unknown building type: '{raw_type}'")
        if company.level < spec["level_required"]:
            raise ValueError(
                f"Company level {company.level} too low. Required level: {spec['level_required']}"
            )
        required_license = spec.get("required_license")
        if required_license:
            await PremiumService.require_active_license(
                session, company.id, required_license, now=get_game_now()
            )

        count_result = await session.execute(
            select(func.count(NatFactory.id)).where(NatFactory.company_id == company.id)
        )
        existing_count = count_result.scalar() or 0
        slots = BuildingService.slot_limits(company, existing_count)
        if slots["free"] <= 0:
            raise ValueError(
                f"No free construction slots. Used {slots['used']}/{slots['max']} slots. Expand territory or level."
            )

        base_cost = float(spec["build_cost"])
        cost = round(base_cost * (1.0 - MasteryService.effect(company, "industry")), 2)
        if company.cash < cost:
            raise ValueError(
                f"Insufficient cash. Cost: {cost:,.0f} cash, available: {company.cash:,.0f} cash"
            )

        is_own = spec["specialization"] == company.specialization
        is_licensed = company.licensed_foreign_spec == spec["specialization"]
        efficiency = 1.0 if is_own else (0.12 if is_licensed else 0.10)
        company.cash = round(company.cash - cost, 2)
        now = get_game_now()
        factory = NatFactory(
            company_id=company.id,
            building_type=spec["id"],
            specialization=spec["specialization"],
            level=1,
            efficiency=efficiency,
            is_active=True,
            workers=spec["workers_required"],
            automation_level=0,
            technology_level=0,
            current_recipe=None,
            cycle_started_at=None,
            cycle_ready_at=None,
            last_produced_at=now,
            created_at=now,
        )
        session.add(factory)
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="SINK", category="factory_build",
            cash_amount=cost, context={"building_type": spec["id"]},
        )
        if commit:
            await session.commit()
            await session.refresh(factory)
        else:
            await session.flush()

        return {
            "success": True,
            "factory_id": factory.id,
            "building_type": factory.building_type,
            "name": spec["name"],
            "cost_paid": cost,
            "base_cost": base_cost,
            "mastery_discount_pct": round(MasteryService.effect(company, "industry") * 100, 2),
            "remaining_cash": company.cash,
            "efficiency": efficiency,
            "specialization": factory.specialization,
        }

    @staticmethod
    async def upgrade_factory(
        session: AsyncSession,
        company: NatCompany,
        factory_id: int,
        upgrade_type: str,
        commit: bool = True,
    ) -> Dict[str, Any]:
        result = await session.execute(
            select(NatFactory).where(
                NatFactory.id == factory_id,
                NatFactory.company_id == company.id,
            )
        )
        factory = result.scalar_one_or_none()
        if not factory:
            raise ValueError("Factory not found")
        if factory.cycle_ready_at:
            raise ValueError("Cannot upgrade while a production cycle is active")

        response = await UpgradeService.upgrade(session, company, factory_id, upgrade_type)
        if commit:
            await session.commit()
        return response

    @staticmethod
    def describe_upgrades(factory: NatFactory, company: NatCompany) -> List[Dict[str, Any]]:
        options = []
        for kind in ("workers", "automation", "technology", "level"):
            info = UpgradeService.describe(company, factory, kind)
            if factory.cycle_ready_at:
                info = {**info, "allowed": False, "reason": "Производственный цикл активен"}
            options.append(info)
        return options


__all__ = ["BuildingService"]
