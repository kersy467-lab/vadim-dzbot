"""Transactional foundation for forming and selling business hybrids."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import HYBRID_RECIPES, get_business_spec
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.hybrid_mergers import NatHybridMerger
from backend.natbirzha.services.business_resource_service import consume_business_resources
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


GLOBAL_ACTIVE_HYBRID_LIMIT = 5
_HYBRID_GLOBAL_LOCK_KEY = 0x4E41544859425249

_SOURCE_STATUSES = frozenset({
    "ACTIVE",
    "PAUSED_MANUAL",
    "PAUSED_SUPPLY",
    "PAUSED_MAINTENANCE",
    "PAUSED_STORAGE",
})


class HybridMergerService:
    """Owns hybrid slot, source business, inventory and additional capital state."""

    @staticmethod
    async def _lock_global_hybrid_capacity(session: AsyncSession) -> None:
        """Serialize global slot changes across app workers on PostgreSQL."""
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": _HYBRID_GLOBAL_LOCK_KEY},
            )
            return

        # Lock a stable server-wide row set on other databases. This is mainly
        # for local SQLite/dev environments, which do not support advisory locks.
        await session.execute(
            select(NatCompany.id).order_by(NatCompany.id).with_for_update()
        )

    @staticmethod
    async def _locked_company(session: AsyncSession, company_id: int) -> NatCompany:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Компания не найдена")
        return company

    @staticmethod
    def _recipe(recipe_id: str) -> dict[str, Any]:
        recipe = HYBRID_RECIPES.get((recipe_id or "").strip().lower())
        if recipe is None:
            raise ValueError("Неизвестный рецепт гибридного предприятия")
        return recipe

    @staticmethod
    async def _locked_sources(
        session: AsyncSession, company_id: int, source_business_ids: tuple[int, int]
    ) -> tuple[NatBusiness, NatBusiness]:
        if source_business_ids[0] == source_business_ids[1]:
            raise ValueError("Для гибрида нужны два разных предприятия")
        rows = (
            await session.execute(
                select(NatBusiness)
                .where(NatBusiness.id.in_(source_business_ids))
                .order_by(NatBusiness.id)
                .with_for_update()
            )
        ).scalars().all()
        if len(rows) != 2:
            raise ValueError("Исходные предприятия не найдены или не принадлежат компании")
        if any(row.company_id != company_id for row in rows):
            raise ValueError("Можно объединять только предприятия своей компании")
        return rows[0], rows[1]

    @classmethod
    async def open_hybrid(
        cls,
        session: AsyncSession,
        company_id: int,
        recipe_id: str,
        source_business_a_id: int,
        source_business_b_id: int,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Form a hybrid, stop its sources, and charge only additional capital."""
        current = normalize_dt(now or get_game_now())
        await IdleEconomyService.settle_company(session, company_id, now=current)
        await cls._lock_global_hybrid_capacity(session)
        company = await cls._locked_company(session, company_id)
        recipe = cls._recipe(recipe_id)
        business_spec = get_business_spec(recipe["business_type"])
        if business_spec is None or not business_spec.get("hybrid_only"):
            raise ValueError("В каталоге отсутствует производственный рецепт гибрида")

        if company.specialization != recipe["specialization"]:
            raise ValueError("Рецепт гибрида недоступен для отрасли вашей компании")

        active_count = int(await session.scalar(
            select(func.count(NatHybridMerger.id)).where(NatHybridMerger.status == "ACTIVE")
        ) or 0)
        if active_count >= GLOBAL_ACTIVE_HYBRID_LIMIT:
            raise ValueError(
                f"Достигнут глобальный максимум: одновременно доступны только {GLOBAL_ACTIVE_HYBRID_LIMIT} гибридов"
            )

        source_a, source_b = await cls._locked_sources(
            session,
            company.id,
            (int(source_business_a_id), int(source_business_b_id)),
        )
        by_type = {source_a.business_type: source_a, source_b.business_type: source_b}
        required_types = tuple(recipe["source_business_types"])
        if set(by_type) != set(required_types):
            raise ValueError("Нужна точная пара предприятий из выбранного рецепта")
        ordered_sources = (by_type[required_types[0]], by_type[required_types[1]])
        for business in ordered_sources:
            if business.specialization != recipe["specialization"]:
                raise ValueError("Исходное предприятие относится к другой отрасли")
            if business.status == "UPGRADING":
                target_stage = int(business.upgrade_target_stage or (business.stage + 1))
                source_spec = get_business_spec(business.business_type) or {}
                source_name = source_spec.get("name", business.business_type)
                raise ValueError(
                    f"Сначала дождитесь улучшения «{source_name}»: "
                    f"уровень {business.stage} → {target_stage}."
                )
            if int(business.stage) < int(recipe["minimum_source_stage"]):
                raise ValueError(
                    f"Каждое исходное предприятие должно быть уровня {recipe['minimum_source_stage']} или выше"
                )
            if business.status not in _SOURCE_STATUSES:
                raise ValueError("Исходное предприятие нельзя объединить в текущем состоянии")

        extra_capital = round(float(business_spec["open_cost"]), 2)
        if extra_capital != round(float(recipe["additional_capital_cost"]), 2):
            raise ValueError("Стоимость гибрида не совпадает с его серверным рецептом")
        if float(company.cash) + 1e-9 < extra_capital:
            raise ValueError("Недостаточно cash для формирования гибрида")

        # The helper locks and checks every required inventory row before it
        # changes any quantity. The caller owns transaction commit/rollback.
        await consume_business_resources(
            session, company.id, recipe["resource_requirements"]
        )

        merger = NatHybridMerger(
            company_id=company.id,
            recipe_id=recipe["id"],
            specialization=recipe["specialization"],
            source_business_a_id=ordered_sources[0].id,
            source_business_b_id=ordered_sources[1].id,
            hybrid_business_id=None,
            source_a_stage=int(ordered_sources[0].stage),
            source_b_stage=int(ordered_sources[1].stage),
            source_a_slot_weight=int(ordered_sources[0].slot_weight),
            source_b_slot_weight=int(ordered_sources[1].slot_weight),
            source_a_status=ordered_sources[0].status,
            source_b_status=ordered_sources[1].status,
            additional_capital_invested=extra_capital,
            status="ACTIVE",
            created_at=current,
        )
        company.cash = round(float(company.cash) - extra_capital, 2)
        for business in ordered_sources:
            business.status = "MERGING"
            business.slot_weight = 0
        session.add(merger)
        await session.flush()
        hybrid_business = NatBusiness(
            company_id=company.id,
            business_type=recipe["business_type"],
            custom_name=business_spec["name"],
            specialization=recipe["specialization"],
            stage=1,
            status="ACTIVE",
            capital_invested=extra_capital,
            base_income_per_hour=float(business_spec["base_income_per_hour"]),
            base_maintenance_per_hour=float(business_spec["base_maintenance_per_hour"]),
            last_settled_at=current,
            slot_weight=int(recipe["hybrid_slot_weight"]),
            metadata_json={
                "sale_mode": "HOLD",
                "hybrid_merger_id": merger.id,
                "hybrid_source_business_ids": [source.id for source in ordered_sources],
            },
        )
        session.add(hybrid_business)
        await session.flush()
        merger.hybrid_business_id = hybrid_business.id
        await session.flush()
        return {
            "success": True,
            "id": merger.id,
            "recipe_id": merger.recipe_id,
            "specialization": merger.specialization,
            "source_business_ids": [merger.source_business_a_id, merger.source_business_b_id],
            "hybrid_business_id": hybrid_business.id,
            "additional_capital_invested": extra_capital,
            "resource_requirements": dict(recipe["resource_requirements"]),
            "remaining_cash": company.cash,
            "active_hybrid_limit": GLOBAL_ACTIVE_HYBRID_LIMIT,
            "active_hybrids": active_count + 1,
        }

    @classmethod
    async def sell_hybrid(
        cls,
        session: AsyncSession,
        company_id: int,
        hybrid_id: int,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Sell a hybrid, restore its saved sources and refund extra capital only."""
        current = normalize_dt(now or get_game_now())
        await IdleEconomyService.settle_company(session, company_id, now=current)
        await cls._lock_global_hybrid_capacity(session)
        company = await cls._locked_company(session, company_id)
        hybrid = await session.scalar(
            select(NatHybridMerger)
            .where(NatHybridMerger.id == int(hybrid_id), NatHybridMerger.company_id == company.id)
            .with_for_update()
        )
        if hybrid is None:
            raise ValueError("Гибрид не найден в вашей компании")
        if hybrid.status != "ACTIVE":
            raise ValueError("Гибрид уже продан")

        recipe = cls._recipe(hybrid.recipe_id)
        hybrid_business = await session.scalar(
            select(NatBusiness)
            .where(
                NatBusiness.id == hybrid.hybrid_business_id,
                NatBusiness.company_id == company.id,
            )
            .with_for_update()
        )
        if hybrid_business is None or hybrid_business.business_type != recipe["business_type"]:
            raise ValueError("Производственное предприятие гибрида не найдено")
        if hybrid_business.status == "UPGRADING":
            raise ValueError("Нельзя продать гибрид во время улучшения")

        source_ids = (hybrid.source_business_a_id, hybrid.source_business_b_id)
        sources = (
            await session.execute(
                select(NatBusiness)
                .where(NatBusiness.id.in_(source_ids))
                .order_by(NatBusiness.id)
                .with_for_update()
            )
        ).scalars().all()
        if len(sources) != 2 or any(source.company_id != company.id for source in sources):
            raise ValueError("Нельзя восстановить исходные предприятия: запись источников повреждена")
        source_by_id = {source.id: source for source in sources}
        source_a = source_by_id[hybrid.source_business_a_id]
        source_b = source_by_id[hybrid.source_business_b_id]
        source_a.stage = int(hybrid.source_a_stage)
        source_b.stage = int(hybrid.source_b_stage)
        source_a.slot_weight = int(hybrid.source_a_slot_weight)
        source_b.slot_weight = int(hybrid.source_b_slot_weight)
        source_a.status = hybrid.source_a_status
        source_b.status = hybrid.source_b_status

        # The hybrid NatBusiness contains only hybrid investment and its
        # upgrades; the two source businesses' original capital never enters
        # this refund calculation.
        hybrid.additional_capital_invested = max(
            float(hybrid.additional_capital_invested),
            float(hybrid_business.capital_invested),
        )
        refund = round(
            max(0.0, float(hybrid.additional_capital_invested))
            * float(recipe["sale_refund_ratio"]),
            2,
        )
        company.cash = round(float(company.cash) + refund, 2)
        hybrid.hybrid_business_id = None
        hybrid.status = "SOLD"
        hybrid.sold_at = current
        await session.delete(hybrid_business)
        await session.flush()
        return {
            "success": True,
            "id": hybrid.id,
            "refund": refund,
            "remaining_cash": company.cash,
            "restored_business_ids": [source_a.id, source_b.id],
            "active_hybrid_limit": GLOBAL_ACTIVE_HYBRID_LIMIT,
        }


__all__ = [
    "GLOBAL_ACTIVE_HYBRID_LIMIT",
    "HYBRID_RECIPES",
    "HybridMergerService",
]
