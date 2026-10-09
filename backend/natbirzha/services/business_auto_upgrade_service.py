"""Minute-tick auto-upgrades for resource businesses, capped at stage nine."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService

AUTO_UPGRADE_MAX_STAGE = 9
AUTO_UPGRADE_RESUMABLE = frozenset({
    "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY", "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
})


class BusinessAutoUpgradeService:
    @staticmethod
    async def set_enabled(session: AsyncSession, company_id: int, enabled: bool) -> dict[str, Any]:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Компания не найдена")
        if company.is_bankrupt and enabled:
            raise ValueError("Включить автоулучшение можно после выхода из банкротства")
        company.auto_upgrade_to_nine_enabled = bool(enabled)
        await session.flush()
        return {
            "success": True,
            "enabled": bool(company.auto_upgrade_to_nine_enabled),
            "max_stage": AUTO_UPGRADE_MAX_STAGE,
        }

    @classmethod
    async def process_company(
        cls,
        session: AsyncSession,
        company_id: int,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        moment = normalize_dt(now or get_game_now())
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id)
            .execution_options(populate_existing=True)
        )
        if company is None or company.is_bankrupt or not company.auto_upgrade_to_nine_enabled:
            return {"company_id": company_id, "started_count": 0, "upgrades": []}

        await IdleEconomyService.settle_company(session, company_id, now=moment)
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if company is None or company.is_bankrupt or not company.auto_upgrade_to_nine_enabled:
            return {"company_id": company_id, "started_count": 0, "upgrades": []}

        businesses = list((await session.scalars(
            select(NatBusiness).where(NatBusiness.company_id == company_id)
            .order_by(NatBusiness.id).with_for_update()
        )).all())
        started: list[dict[str, Any]] = []
        for business in businesses:
            spec = get_business_spec(business.business_type)
            if (
                spec is None
                or spec.get("legacy_hidden")
                or business.status not in AUTO_UPGRADE_RESUMABLE
                or (business.metadata_json or {}).get("contract_expired")
                or int(business.stage) >= AUTO_UPGRADE_MAX_STAGE
                or int(business.stage) >= int(spec["max_stage"])
            ):
                continue
            quote = BusinessService.upgrade_quote(spec, int(business.stage))
            if int(quote["target_stage"]) > AUTO_UPGRADE_MAX_STAGE:
                continue
            try:
                result = await BusinessService.start_upgrade(
                    session, company_id, business.id, now=moment, _skip_settlement=True
                )
            except ValueError:
                # Missing funds, inputs, or project slots wait for the next tick.
                continue
            started.append({
                "business_id": business.id,
                "target_stage": int(result["target_stage"]),
                "cost": float(result["cost"]),
            })

        await session.flush()
        return {"company_id": company_id, "started_count": len(started), "upgrades": started}

    @classmethod
    async def process_enabled_companies(
        cls, session: AsyncSession, *, now: datetime | None = None
    ) -> dict[str, int]:
        ids = list((await session.scalars(
            select(NatCompany.id).where(
                NatCompany.auto_upgrade_to_nine_enabled.is_(True),
                NatCompany.is_bankrupt.is_(False),
            ).order_by(NatCompany.id)
        )).all())
        started = 0
        for company_id in ids:
            result = await cls.process_company(session, company_id, now=now)
            started += int(result["started_count"])
            await session.commit()
        return {"companies_checked": len(ids), "upgrades_started": started}


__all__ = ["AUTO_UPGRADE_MAX_STAGE", "BusinessAutoUpgradeService"]
