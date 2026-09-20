"""Read-only, player-facing explanations for a factory's next production step."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.recipes import get_recipe, get_recipe_for_factory


def describe_factory_start_hint(
    company: NatCompany,
    factory: NatFactory,
    available_inventory: dict[str, float],
    active_license_codes: set[str],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Return the first server-derived blocker, without mutating game state."""

    if not factory.is_active:
        return {"reason": "factory_inactive", "message": "Предприятие отключено.", "next_action": "contact_creator"}
    if factory.cycle_ready_at:
        if now >= factory.cycle_ready_at:
            return {"reason": "cycle_ready_to_collect", "message": "Цикл готов: заберите продукцию.", "next_action": "collect"}
        return {"reason": "cycle_in_progress", "message": "Цикл уже выполняется.", "next_action": "wait"}

    recipe = get_recipe(factory.current_recipe) if factory.current_recipe else get_recipe_for_factory(factory.building_type)
    if not recipe or recipe.get("specialization") != factory.specialization:
        return {"reason": "recipe_not_available", "message": "Для этого предприятия нет доступного рецепта.", "next_action": "check_recipe"}
    if company.level < int(recipe.get("level_req", 1)):
        required_level = int(recipe["level_req"])
        return {"reason": "company_level_required", "message": f"Нужен уровень компании {required_level}.", "next_action": "gain_xp", "required_level": required_level}

    required_license = recipe.get("required_license")
    if required_license and required_license not in active_license_codes:
        return {"reason": "premium_license_required", "message": "Нужна активная лицензия PVC для редкой добычи.", "next_action": "open_premium", "required_license": required_license}
    labor_demand = int(recipe.get("labor_demand", 0))
    if factory.workers < labor_demand:
        return {"reason": "insufficient_labor", "message": f"Нужно работников: {labor_demand}, доступно: {factory.workers}.", "next_action": "upgrade_workers", "needed": labor_demand, "available": factory.workers}

    input_multiplier = max(1, factory.level)
    for item_id, quantity in recipe.get("inputs", {}).items():
        needed = round(float(quantity) * input_multiplier, 4)
        available = float(available_inventory.get(item_id, 0))
        if available < needed:
            return {"reason": "insufficient_input", "message": f"Не хватает сырья «{item_id}»: нужно {needed}, на складе {available}.", "next_action": "open_market", "item_id": item_id, "needed": needed, "available": available}

    return {"reason": "ready", "message": "Можно запустить производственный цикл.", "next_action": "start_cycle"}


__all__ = ["describe_factory_start_hint"]
