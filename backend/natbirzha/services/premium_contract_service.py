"""Persistent enterprises granted by time-limited PVC contracts."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.business_capacity_service import BusinessCapacityService


class PremiumContractService:
    """Keep leased V2 businesses and their upgrades between renewals."""

    LICENSE_CODE = "rare_mining"
    BUSINESS_TYPE = "lithium_quarry_v2"

    @classmethod
    async def _existing_business(
        cls, session: AsyncSession, company_id: int
    ) -> NatBusiness | None:
        return await session.scalar(
            select(NatBusiness)
            .where(
                NatBusiness.company_id == company_id,
                NatBusiness.business_type == cls.BUSINESS_TYPE,
            )
            .order_by(NatBusiness.id)
            .limit(1)
            .with_for_update()
        )

    @classmethod
    async def validate_rare_mining_purchase(
        cls, session: AsyncSession, company_id: int
    ) -> None:
        if await cls._existing_business(session, company_id) is not None:
            return
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Компания не найдена")
        spec = get_business_spec(cls.BUSINESS_TYPE)
        if spec is None:
            raise ValueError("Литиевый карьер отсутствует в каталоге")
        if int(company.level) < int(spec.get("company_level_required", 1)):
            raise ValueError(
                f"Для контракта на литиевый карьер нужен уровень компании {spec['company_level_required']}"
            )
        if int(company.territory_tiles) < int(spec.get("territory_required", 0)):
            raise ValueError(
                f"Для контракта на литиевый карьер нужна территория {spec['territory_required']} ед."
            )

        used = await BusinessService._used_slots(session, company_id)
        slots = BusinessCapacityService.slot_limits(company, used=used)
        if slots["free"] < int(spec["slot_weight"]):
            raise ValueError(
                f"Для контрактного карьера нужна свободная корпоративная мощность ({slots['used']}/{slots['max']})"
            )

    @classmethod
    async def grant_rare_mining_business(
        cls, session: AsyncSession, company_id: int, *, now: datetime
    ) -> NatBusiness:
        existing = await cls._existing_business(session, company_id)
        if existing is not None:
            metadata = dict(existing.metadata_json or {})
            metadata["contract_license"] = cls.LICENSE_CODE
            metadata.pop("contract_expired", None)
            resume_status = metadata.pop("contract_resume_status", "ACTIVE")
            existing.metadata_json = metadata
            if existing.status == "PAUSED_MANUAL":
                existing.status = resume_status if resume_status in {
                    "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY",
                    "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
                } else "ACTIVE"
            await session.flush()
            return existing

        await cls.validate_rare_mining_purchase(session, company_id)
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        spec = get_business_spec(cls.BUSINESS_TYPE)
        if company is None or spec is None:
            raise ValueError("Не удалось выдать контрактный литиевый карьер")
        business = NatBusiness(
            company_id=company.id,
            business_type=cls.BUSINESS_TYPE,
            custom_name=spec["name"],
            specialization=spec["specialization"],
            stage=1,
            status="ACTIVE",
            capital_invested=0.0,
            base_income_per_hour=float(spec["base_income_per_hour"]),
            base_maintenance_per_hour=float(spec["base_maintenance_per_hour"]),
            last_settled_at=now,
            health=100.0,
            efficiency=1.0,
            slot_weight=int(spec["slot_weight"]),
            metadata_json={"contract_license": cls.LICENSE_CODE, "sale_mode": "NPC"},
            created_at=now,
        )
        session.add(business)
        await session.flush()
        return business


__all__ = ["PremiumContractService"]
