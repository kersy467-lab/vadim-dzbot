"""Exclusive rare-resource military upgrade branch checks."""

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.combat_resolver import ArmySnapshot, resolve_battle
from backend.natbirzha.services.premium_service import PremiumLicenseRequired, PremiumService
from backend.natbirzha.services.premium_upgrade_service import PremiumUpgradeService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        company = NatCompany(user_id=975001, name="Advanced Defense", specialization="technoprom")
        no_license = NatCompany(user_id=975002, name="No License", specialization="miner")
        session.add_all([company, no_license])
        await session.flush()
        item_ids = ("rare_earths", "lithium_raw", "cobalt_raw", "gallium_raw", "electronics", "steel")
        for owner in (company, no_license):
            for item_id in item_ids:
                session.add(NatInventory(company_id=owner.id, item_id=item_id, quantity=100.0))
        await session.commit()

        try:
            await PremiumUpgradeService.purchase_upgrade(
                session, no_license.id, "precision_guidance", now=datetime(2026, 9, 19, 12)
            )
        except PremiumLicenseRequired as exc:
            assert exc.license_code == "advanced_defense"
        else:
            raise AssertionError("Premium military upgrades require advanced_defense license")

        await PremiumService.apply_pvc(
            session, company.id, 500, "test_credit", "upgrade-credit", {}
        )
        now = datetime(2026, 9, 19, 12)
        await PremiumService.purchase_license(
            session, company.id, "advanced_defense", "advanced-license", now=now
        )
        for code in (
            "electronic_warfare",
            "active_protection",
            "precision_guidance",
            "autonomous_strike_drones",
        ):
            upgrade = await PremiumUpgradeService.purchase_upgrade(session, company.id, code, now=now)
            assert upgrade.level == 1

        modifiers = await PremiumUpgradeService.modifiers(session, company.id)
        assert modifiers.electronic_warfare == 0.04
        assert modifiers.active_protection == 0.05
        assert modifiers.air == 0.04
        assert modifiers.recon == 0.04

        await PremiumUpgradeService.purchase_upgrade(session, company.id, "precision_guidance", now=now)
        maxed = await PremiumUpgradeService.purchase_upgrade(
            session, company.id, "precision_guidance", now=now
        )
        assert maxed.level == 3
        modifiers = await PremiumUpgradeService.modifiers(session, company.id)
        assert modifiers.air == 0.12
        try:
            await PremiumUpgradeService.purchase_upgrade(
                session, company.id, "precision_guidance", now=now
            )
        except ValueError as exc:
            assert "maximum" in str(exc).lower()
        else:
            raise AssertionError("Upgrade level cap must be enforced")

        baseline = resolve_battle(
            ArmySnapshot(units={"aircraft": 2}),
            ArmySnapshot(units={"tanks": 3}),
            seed="premium-upgrade",
        )
        enhanced = resolve_battle(
            ArmySnapshot(units={"aircraft": 2}),
            ArmySnapshot(units={"tanks": 3}),
            seed="premium-upgrade",
            attacker_modifiers=modifiers,
        )
        assert enhanced.attacker_score > baseline.attacker_score

    await engine.dispose()
    print("NATBIRZHA premium military-upgrade checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())

