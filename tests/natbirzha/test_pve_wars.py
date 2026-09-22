"""PvE corporate-war transaction, reward, rating, and replay checks."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.combat import NatArmyUnit, NatBattle, NatPveVictory
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.pve_service import PveService, PveWarError
from backend.natbirzha.services.pve_catalog import PVE_CORPORATIONS, PVE_FORCE_REQUIREMENTS
from backend.natbirzha.services.progression_service import xp_required_for_level


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        strong = NatCompany(
            user_id=930001,
            name="Strong Corp",
            specialization="technoprom",
            cash=50_000,
            territory_tiles=4,
            military_rating=1000, level=6,
        )
        weak = NatCompany(
            user_id=930002,
            name="Weak Corp",
            specialization="agrarian",
            cash=50_000,
            territory_tiles=4,
            military_rating=1000, level=6,
        )
        infantry_rusher = NatCompany(
            user_id=930003,
            name="Infantry Rush Corp",
            specialization="agrarian",
            cash=50_000,
            territory_tiles=4,
            military_rating=1000, level=6,
        )
        session.add_all([strong, weak, infantry_rusher])
        await session.flush()
        session.add_all(
            [
                NatArmyUnit(company_id=strong.id, unit_type="infantry", quantity=500),
                NatArmyUnit(company_id=strong.id, unit_type="border_guards", quantity=20),
                NatArmyUnit(company_id=strong.id, unit_type="tanks", quantity=10),
                NatArmyUnit(company_id=strong.id, unit_type="drones", quantity=10),
                NatInventory(company_id=strong.id, item_id="food", quantity=1000.0, reserved_quantity=0.0),
                NatInventory(company_id=strong.id, item_id="fuel_diesel", quantity=1000.0, reserved_quantity=0.0),
                NatInventory(company_id=strong.id, item_id="military_gear", quantity=1000.0, reserved_quantity=0.0),
                NatArmyUnit(company_id=weak.id, unit_type="infantry", quantity=100),
                NatArmyUnit(company_id=weak.id, unit_type="border_guards", quantity=20),
                NatArmyUnit(company_id=weak.id, unit_type="drones", quantity=5),
                NatInventory(company_id=weak.id, item_id="food", quantity=1000.0, reserved_quantity=0.0),
                NatInventory(company_id=weak.id, item_id="fuel_diesel", quantity=1000.0, reserved_quantity=0.0),
                NatInventory(company_id=weak.id, item_id="military_gear", quantity=1000.0, reserved_quantity=0.0),
                # 400 infantry cost 20k cash. This used to be enough to brute-force PvE.
                NatArmyUnit(company_id=infantry_rusher.id, unit_type="infantry", quantity=400),
            ]
        )
        await session.commit()

        try:
            await PveService.attack_target(
                session,
                infantry_rusher,
                "local_logistics",
                "pve:infantry-rush:1",
                now=datetime(2026, 9, 18, 11, 30, 0),
            )
        except PveWarError as exc:
            assert exc.reason == "insufficient_force_composition"
        else:
            raise AssertionError("20k cash of infantry must not be able to brute-force PvE")

        targets = await PveService.list_targets(session, strong)
        assert len(targets) == 12
        assert PVE_CORPORATIONS[0]["min_company_level"] == 6
        assert PVE_FORCE_REQUIREMENTS[1]["ground_total"] >= 100
        assert PVE_FORCE_REQUIREMENTS[4]["aircraft"] >= 20
        assert [row["tier"] for row in targets].count(1) == 3
        assert any(row["available"] is False for row in targets)
        assert all(row["army_requirements"] for row in targets)
        assert all(row["strength_range"]["min"] < row["strength_range"]["max"] for row in targets)
        scout = await PveService.scout_target(session, strong, "local_logistics")
        assert scout["accuracy"] == "estimated" and scout["known_units"] is None
        assert scout["risk"] in {"low", "medium", "high", "extreme"}
        assert set(scout["expected_losses"]) == {
            "infantry", "border_guards", "tanks", "drones", "aircraft", "air_defense"
        }
        assert all(row["min"] <= row["max"] for row in scout["expected_losses"].values())

        before_cash = strong.cash
        before_territory = strong.territory_tiles
        victory = await PveService.attack_target(
            session,
            strong,
            "local_logistics",
            "pve:strong:1",
            now=datetime(2026, 9, 18, 12, 0, 0),
        )
        assert victory["winner"] == "attacker"
        assert victory["territory_awarded"] == 1
        assert strong.territory_tiles == before_territory + 1
        assert strong.cash > before_cash
        assert strong.military_rating > 1000
        territory_after = strong.territory_tiles
        cash_after = strong.cash
        rating_after = strong.military_rating

        replay = await PveService.attack_target(
            session,
            strong,
            "local_logistics",
            "pve:strong:1",
            now=datetime(2026, 9, 18, 12, 1, 0),
        )
        assert replay == victory
        assert (strong.territory_tiles, strong.cash, strong.military_rating) == (
            territory_after,
            cash_after,
            rating_after,
        )

        try:
            await PveService.attack_target(
                session,
                strong,
                "local_logistics",
                "pve:strong:2",
                now=datetime(2026, 9, 18, 12, 2, 0),
            )
        except PveWarError as exc:
            assert exc.reason == "cooldown"
        else:
            raise AssertionError("Winning against one PvE corporation must start its two-hour cooldown")

        # Combat losses remain real: replenish the expedition before a rematch.
        strong_units = (await session.execute(
            select(NatArmyUnit).where(NatArmyUnit.company_id == strong.id)
        )).scalars().all()
        for unit in strong_units:
            if unit.unit_type == "infantry":
                unit.quantity = max(unit.quantity, 500)
            elif unit.unit_type == "border_guards":
                unit.quantity = max(unit.quantity, 25)
            elif unit.unit_type == "drones":
                unit.quantity = max(unit.quantity, 10)
        strong.level = 60
        strong.xp = xp_required_for_level(60)
        strong.mastery_xp = 0
        strong.mastery_rank = 0
        await session.flush()
        rematch = await PveService.attack_target(
            session,
            strong,
            "local_logistics",
            "pve:strong:3",
            now=datetime(2026, 9, 18, 12, 0, 0) + timedelta(hours=2, minutes=1),
        )
        assert rematch["winner"] == "attacker"
        assert rematch["campaign_rank"] == 1
        assert rematch["territory_awarded"] == 0
        assert strong.mastery_xp == rematch["rewards"]["xp"]

        defeat = await PveService.attack_target(
            session,
            weak,
            "local_logistics",
            "pve:weak:1",
            now=datetime(2026, 9, 18, 13, 0, 0),
        )
        assert defeat["winner"] == "defender"
        assert defeat["territory_awarded"] == 0
        assert weak.territory_tiles == 4
        assert weak.military_rating < 1000
        await session.commit()

        battle_count = await session.scalar(select(func.count()).select_from(NatBattle))
        victory_count = await session.scalar(select(func.count()).select_from(NatPveVictory))
        assert battle_count == 3
        assert victory_count == 1

    await engine.dispose()
    print("NATBIRZHA PvE corporate-war checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
