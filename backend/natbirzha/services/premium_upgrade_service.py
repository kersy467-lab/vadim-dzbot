"""Persistent late-game military upgrades built from premium rare resources."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.premium import NatMilitaryUpgrade
from backend.natbirzha.services.combat_resolver import PremiumModifiers
from backend.natbirzha.services.premium_catalog import MILITARY_UPGRADES
from backend.natbirzha.services.premium_service import PremiumService


class PremiumUpgradeService:
    @classmethod
    async def purchase_upgrade(
        cls,
        session: AsyncSession,
        company_id: int,
        upgrade_code: str,
        *,
        now: datetime | None = None,
    ) -> NatMilitaryUpgrade:
        spec = MILITARY_UPGRADES.get(upgrade_code)
        if spec is None:
            raise ValueError(f"Unknown premium military upgrade: {upgrade_code}")
        now = now or datetime.utcnow()
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Company not found")
        await PremiumService.require_active_license(
            session, company_id, spec.required_license, now=now
        )
        upgrade = await session.scalar(
            select(NatMilitaryUpgrade)
            .where(
                NatMilitaryUpgrade.company_id == company_id,
                NatMilitaryUpgrade.upgrade_code == upgrade_code,
            )
            .with_for_update()
        )
        current_level = upgrade.level if upgrade else 0
        if current_level >= spec.max_level:
            raise ValueError("Premium military upgrade reached maximum level")
        next_level = current_level + 1

        inventories = (
            await session.execute(
                select(NatInventory)
                .where(
                    NatInventory.company_id == company_id,
                    NatInventory.item_id.in_(tuple(spec.resource_cost)),
                )
                .with_for_update()
            )
        ).scalars().all()
        by_item = {row.item_id: row for row in inventories}
        for item_id, base_quantity in spec.resource_cost.items():
            required = base_quantity * next_level
            inventory = by_item.get(item_id)
            available = inventory.available_quantity if inventory else 0.0
            if available < required:
                raise ValueError(
                    f"Insufficient {item_id}. Required: {required}, Available: {available}"
                )
        for item_id, base_quantity in spec.resource_cost.items():
            by_item[item_id].quantity -= base_quantity * next_level

        if upgrade is None:
            upgrade = NatMilitaryUpgrade(
                company_id=company_id,
                upgrade_code=upgrade_code,
                level=1,
                created_at=now,
                updated_at=now,
            )
            session.add(upgrade)
        else:
            upgrade.level = next_level
            upgrade.updated_at = now
        await session.flush()
        return upgrade

    @staticmethod
    async def owned(session: AsyncSession, company_id: int) -> list[NatMilitaryUpgrade]:
        return list(
            (
                await session.execute(
                    select(NatMilitaryUpgrade)
                    .where(NatMilitaryUpgrade.company_id == company_id)
                    .order_by(NatMilitaryUpgrade.upgrade_code)
                )
            ).scalars().all()
        )

    @classmethod
    async def modifiers(cls, session: AsyncSession, company_id: int) -> PremiumModifiers:
        values = {
            "recon": 0.0,
            "air": 0.0,
            "ground": 0.0,
            "defense": 0.0,
            "electronic_warfare": 0.0,
            "active_protection": 0.0,
        }
        for upgrade in await cls.owned(session, company_id):
            spec = MILITARY_UPGRADES.get(upgrade.upgrade_code)
            if spec:
                values[spec.modifier] += spec.modifier_per_level * upgrade.level
        return PremiumModifiers(**values)
