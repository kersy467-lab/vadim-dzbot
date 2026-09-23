"""Server-side NPC margin estimates for recipe-based factory catalog entries."""

from typing import Any, Mapping

from backend.natbirzha.models.inventory import get_npc_buy_price, get_npc_sell_price


def estimate_building_economics(
    building: Mapping[str, Any],
    *,
    efficiency: float,
    build_cost: float,
) -> dict[str, float | None]:
    """Estimate NPC-only operating margin and simple construction payback."""
    revenue = sum(
        float(quantity) * get_npc_buy_price(item_id)
        for item_id, quantity in building.get("outputs", {}).items()
    ) * max(0.0, float(efficiency))
    input_cost = sum(
        float(quantity) * get_npc_sell_price(item_id)
        for item_id, quantity in building.get("inputs", {}).items()
    )
    net_per_cycle = round(revenue - input_cost, 2)
    duration = max(1, int(building.get("cycle_duration") or 1))
    net_per_hour = round(net_per_cycle * 3600 / duration, 2)
    payback_hours = (
        round(float(build_cost) / net_per_hour, 2)
        if net_per_hour > 0
        else None
    )
    return {
        "net_per_cycle": net_per_cycle,
        "net_per_hour": net_per_hour,
        "payback_hours": payback_hours,
    }


__all__ = ["estimate_building_economics"]
