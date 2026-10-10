"""Production settlement and inventory operations for NATBIRZHA 2.0."""
from datetime import datetime, timedelta
from math import floor
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility, NatNextGameInventory
from backend.natbirzha.next_game_catalog import find_next_game_branch, get_next_game_items
from .common import (
    MAX_CATCH_UP_CYCLES, XP_PER_CYCLE, XP_PER_LEVEL,
    MAX_INVENTORY_PER_ITEM, _utcnow, facility_recipe_at_level,
)

class NextGameProductionMixin:
    @classmethod
    async def settle_company(
        cls, session: AsyncSession, owner_tg_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        treasury = await cls._treasury(session)
        current = now or _utcnow()
        from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService
        from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService
        from backend.natbirzha.services.next_game_operations_effects import factory_recipe, complete_cycle
        from backend.natbirzha.services.next_game_civic_accounting import event_multiplier
        bonus = await NextGameProgressionService.production_bonus(session, company)
        facilities = list((await session.scalars(
            select(NatNextGameFacility).where(NatNextGameFacility.company_id == company.id)
            .order_by(NatNextGameFacility.id).with_for_update()
        )).all())
        completed = 0
        blocked: list[dict[str, str]] = []
        for facility in facilities:
            branch = find_next_game_branch(facility.branch_id)
            if not branch:
                continue
            base_recipe = await NextGameFusionService.facility_recipe(session, facility, branch["factory"])
            level_recipe = facility_recipe_at_level(base_recipe, facility.level)
            interval = int(level_recipe["cycle_seconds"])
            if current < facility.next_cycle_at:
                continue
            due = min(MAX_CATCH_UP_CYCLES, 1 + floor(
                (current - facility.next_cycle_at).total_seconds() / interval
            ))
            for _ in range(due):
                event_bonus = await event_multiplier(session, company, now=facility.next_cycle_at)
                cycle_recipe = {**level_recipe,
                    "output_quantity": round(level_recipe["output_quantity"] * bonus * event_bonus, 4)}
                recipe = await factory_recipe(session, company, facility, cycle_recipe, now=facility.next_cycle_at)
                reason = await cls._cycle_block_reason(session, company, recipe)
                if reason:
                    blocked.append({"facility_id": str(facility.id), "reason": reason})
                    facility.next_cycle_at = current + timedelta(seconds=interval)
                    break
                from backend.natbirzha.services.next_game_active_production_service import (
                    active_multiplier_for_cycle, output_with_active_bonus,
                )
                cycle_end = facility.next_cycle_at
                cycle_start = cycle_end - timedelta(seconds=interval)
                active_multiplier, active_seconds = await active_multiplier_for_cycle(
                    session, company.id, cycle_start, cycle_end,
                )
                base_output = float(recipe["output_quantity"])
                active_bonus_output = 0.0
                if active_multiplier > 1:
                    from backend.natbirzha.services.next_game_market_service import NextGameMarketService
                    from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
                    inventory = await cls._inventory_row(session, company.id, recipe["output_item"])
                    reserved = await NextGameMarketService.reserved_sell_quantity(
                        session, company.id, recipe["output_item"],
                    )
                    recipe["output_quantity"], active_bonus_output = output_with_active_bonus(
                        base_output,
                        active_multiplier,
                        await warehouse_capacity(session, company.id),
                        float(inventory.quantity if inventory else 0),
                        reserved,
                    )
                for item_id, quantity in recipe["inputs"].items():
                    await cls._change_inventory(session, company.id, item_id, -float(quantity))
                    session.add(cls._ledger(
                        company.id, "PRODUCTION_INPUT", 0, 0, item_id=item_id,
                        company_quantity=-float(quantity), metadata={"facility_id": facility.id},
                    ))
                cost = float(recipe["operating_cost"])
                company.cash = round(float(company.cash) - cost, 8)
                treasury.cash = round(float(treasury.cash) + cost, 8)
                session.add(cls._ledger(company.id, "OPERATING_COST", -cost, cost, metadata={"facility_id": facility.id}))
                output_id = recipe["output_item"]
                await cls._change_inventory(session, company.id, output_id, float(recipe["output_quantity"]))
                session.add(cls._ledger(
                    company.id, "PRODUCTION_OUTPUT", 0, 0, item_id=output_id,
                    company_quantity=float(recipe["output_quantity"]), metadata={
                        "facility_id": facility.id,
                        "active_production_multiplier": active_multiplier,
                        "active_seconds": active_seconds,
                        "bonus_output": active_bonus_output,
                    },
                ))
                completed += 1
                await complete_cycle(session, facility)
                company.xp = int(company.xp) + XP_PER_CYCLE
                company.level = min(60, 1 + int(company.xp) // XP_PER_LEVEL)
                facility.next_cycle_at += timedelta(seconds=interval)
        from backend.natbirzha.services.next_game_auto_upgrade_service import auto_upgrade_company
        await auto_upgrade_company(session, cls, company, current)
        await session.flush()
        return {"cycles_completed": completed, "blocked": blocked}

    @classmethod
    async def _cycle_block_reason(
        cls, session: AsyncSession, company: NatNextGameCompany, recipe: dict[str, Any]
    ) -> str | None:
        if float(company.cash) + 1e-9 < float(recipe["operating_cost"]):
            return "Недостаточно cash на расходы цикла"
        for item_id, needed in recipe["inputs"].items():
            row = await cls._inventory_row(session, company.id, item_id)
            if row is None or float(row.quantity) + 1e-9 < float(needed):
                items = get_next_game_items()
                return f"Нужен ресурс: {items[item_id]['name']} — {needed:g} {items[item_id]['unit']}"
        output = await cls._inventory_row(session, company.id, recipe["output_item"])
        from backend.natbirzha.services.next_game_market_service import NextGameMarketService

        reserved_output = await NextGameMarketService.reserved_sell_quantity(
            session, company.id, recipe["output_item"],
        )
        from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
        if (float(output.quantity if output else 0.0) + reserved_output
                + float(recipe["output_quantity"]) > await warehouse_capacity(session, company.id)):
            return "Склад заполнен; продайте готовый товар"
        return None

    @classmethod
    async def _change_inventory(
        cls, session: AsyncSession, company_id: int, item_id: str, delta: float,
        *, row: NatNextGameInventory | None = None,
    ) -> NatNextGameInventory:
        inventory = row or await cls._inventory_row(session, company_id, item_id)
        if inventory is None:
            if delta < 0:
                raise ValueError("Недостаточно товара на складе 2.0")
            inventory = NatNextGameInventory(company_id=company_id, item_id=item_id, quantity=0)
            session.add(inventory)
            await session.flush()
        next_value = round(float(inventory.quantity) + delta, 4)
        if next_value < -1e-7:
            raise ValueError("Недостаточно товара на складе 2.0")
        inventory.quantity = max(0.0, next_value)
        return inventory

    @staticmethod
    async def _inventory_row(
        session: AsyncSession, company_id: int, item_id: str
    ) -> NatNextGameInventory | None:
        return await session.scalar(
            select(NatNextGameInventory).where(
                NatNextGameInventory.company_id == company_id,
                NatNextGameInventory.item_id == item_id,
            ).with_for_update()
        )
