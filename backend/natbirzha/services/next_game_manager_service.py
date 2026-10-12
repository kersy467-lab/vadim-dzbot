"""Guaranteed manager milestones and one-factory production bonuses."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_managers import NatNextGameManager


MANAGER_REWARDS = (
    (5, "Amelia Brooks", "common", 2),
    (15, "Ethan Cole", "rare", 4),
    (30, "Sofia Bennett", "epic", 6),
    (45, "Lucas Morgan", "legendary", 8),
)

PRODUCTION_BONUS_BY_RARITY = {
    "common": 8,
    "rare": 9,
    "epic": 10,
    "legendary": 10,
}


async def ensure_manager_awards(session: AsyncSession, company: NatNextGameCompany):
    """Backfill each reached milestone once, including for older V2 accounts."""
    rows = list((await session.scalars(select(NatNextGameManager).where(
        NatNextGameManager.company_id == company.id,
    ).order_by(NatNextGameManager.reward_level))).all())
    reward_by_level = {
        level: (name, rarity, legacy_storage_code)
        for level, name, rarity, legacy_storage_code in MANAGER_REWARDS
    }
    existing = {
        row.reward_level for row in rows
        if row.source == "milestone"
    }
    # Normalize names already issued by earlier releases without changing the
    # employee's rarity, discount, assignment, or award level.
    for row in rows:
        reward = reward_by_level.get(row.reward_level) if row.source == "milestone" else None
        if reward:
            row.name = reward[0]
            row.level = int(row.reward_level)
    for level, name, rarity, legacy_storage_code in MANAGER_REWARDS:
        if int(company.level) >= level and level not in existing:
            row = NatNextGameManager(
                company_id=company.id, reward_level=level, name=name,
                rarity=rarity, discount_pct=legacy_storage_code,
                source="milestone", level=level,
            )
            session.add(row)
            rows.append(row)
    if rows:
        await session.flush()
    return rows


async def manager_output_bonus_pct(session: AsyncSession, facility_id: int) -> int:
    rarity = await session.scalar(select(NatNextGameManager.rarity).where(
        NatNextGameManager.facility_id == facility_id,
    ))
    return PRODUCTION_BONUS_BY_RARITY.get(str(rarity or ""), 0)


def apply_manager_output_bonus(recipe: dict, bonus_pct: float) -> dict:
    """Increase product output only; inputs and operating cash costs stay fixed."""
    before = max(0.0, float(recipe.get("output_quantity", 0)))
    bonus = max(0.0, min(10.0, float(bonus_pct))) / 100
    after = round(before * (1 + bonus), 4)
    additional_output = after - before
    recipe["output_quantity"] = after
    if "net_output_quantity" in recipe:
        recipe["net_output_quantity"] = round(float(recipe["net_output_quantity"]) + additional_output, 4)
    recipe["manager_production_bonus_pct"] = int(round(bonus * 100))
    economics = recipe.get("economics")
    if isinstance(economics, dict) and before > 0 and additional_output > 0:
        revenue_before = float(economics.get("npc_revenue", 0))
        unit_price = revenue_before / before
        added_revenue = additional_output * unit_price
        if "npc_revenue" in economics:
            economics["npc_revenue"] = round(revenue_before + added_revenue, 2)
        profit = float(economics.get("npc_profit", 0)) + added_revenue
        hours = max(1e-9, float(recipe.get("cycle_seconds", 3600)) / 3600)
        economics["npc_profit"] = round(profit, 2)
        economics["profit_per_hour"] = round(profit / hours, 2)
        build_cost = float(recipe.get("build_cost", 0))
        economics["payback_cycles"] = round(build_cost / profit, 2) if profit > 0 else None
    return recipe


async def assign_manager(
    session: AsyncSession, owner_tg_id: int, manager_id: int,
    branch_id: str | None,
) -> dict:
    from backend.natbirzha.services.next_game_service import NextGameService

    await NextGameService._lock_treasury_for_sqlite(session)
    await NextGameService.settle_company(session, owner_tg_id)
    company = await NextGameService._owned_company(session, owner_tg_id)
    managers = await ensure_manager_awards(session, company)
    manager = next((row for row in managers if row.id == int(manager_id)), None)
    if manager is None:
        raise ValueError("Этот менеджер не принадлежит вашей компании")
    facility = None
    if branch_id:
        facility = await session.scalar(select(NatNextGameFacility).where(
            NatNextGameFacility.company_id == company.id,
            NatNextGameFacility.branch_id == branch_id,
        ).with_for_update())
        if facility is None:
            raise ValueError("Сначала постройте завод для назначения менеджера")
        occupied = await session.scalar(select(NatNextGameManager).where(
            NatNextGameManager.company_id == company.id,
            NatNextGameManager.facility_id == facility.id,
            NatNextGameManager.id != manager.id,
        ).with_for_update())
        if occupied:
            raise ValueError("На завод уже назначен менеджер; сначала снимите его")
    manager.facility_id = facility.id if facility else None
    await session.flush()
    return {
        "success": True, "manager": manager_payload(manager, facility.branch_id if facility else None),
    }


def manager_payload(manager: NatNextGameManager, branch_id: str | None = None) -> dict:
    return {
        "id": manager.id, "name": manager.name, "rarity": manager.rarity,
        "source": manager.source, "level": int(manager.level),
        "reward_level": manager.reward_level,
        "production_bonus_pct": PRODUCTION_BONUS_BY_RARITY.get(manager.rarity, 0),
        "facility_id": manager.facility_id, "branch_id": branch_id,
    }


__all__ = [
    "MANAGER_REWARDS", "PRODUCTION_BONUS_BY_RARITY", "ensure_manager_awards",
    "manager_output_bonus_pct", "apply_manager_output_bonus",
    "assign_manager", "manager_payload",
]
