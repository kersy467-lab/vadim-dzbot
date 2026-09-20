"""P2 schema invariants for premium currency, combat, and tournaments."""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from backend.db.models import Base
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.combat import (
    NatArmyUnit,
    NatBattle,
    NatBattleSnapshot,
    NatMilitaryRatingEvent,
    NatPveCorporation,
    NatPveVictory,
    NatPvpCooldown,
)
from backend.natbirzha.models.premium import NatMilitaryUpgrade, NatPremiumLedgerEntry, NatPremiumLicense


async def run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    expected = {
        "nat_army_units",
        "nat_battles",
        "nat_battle_snapshots",
        "nat_military_rating_events",
        "nat_pve_corporations",
        "nat_pve_victories",
        "nat_pvp_cooldowns",
        "nat_premium_ledger",
        "nat_premium_licenses",
        "nat_military_upgrades",
    }
    assert expected.issubset(Base.metadata.tables)

    assert NatCompany.__table__.c.pvc_balance.default.arg == 0
    assert NatCompany.__table__.c.military_rating.default.arg == 1000

    army_constraints = {c.name for c in NatArmyUnit.__table__.constraints}
    ledger_constraints = {c.name for c in NatPremiumLedgerEntry.__table__.constraints}
    victory_constraints = {c.name for c in NatPveVictory.__table__.constraints}
    cooldown_constraints = {c.name for c in NatPvpCooldown.__table__.constraints}
    assert "uq_nat_army_unit_company_type" in army_constraints
    assert "uq_nat_premium_ledger_operation_key" in ledger_constraints
    upgrade_constraints = {c.name for c in NatMilitaryUpgrade.__table__.constraints}
    assert "uq_nat_military_upgrade_company_code" in upgrade_constraints
    assert "uq_nat_pve_victory_company_target" in victory_constraints
    assert "uq_nat_pvp_cooldown_pair" in cooldown_constraints

    await engine.dispose()
    print("NATBIRZHA P2 model checks: PASS")


if __name__ == "__main__":
    asyncio.run(run())
