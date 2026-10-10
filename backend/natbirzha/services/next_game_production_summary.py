"""Aggregate runway and comparable production margins without database queries."""
from backend.natbirzha.next_game_catalog import get_next_game_items


def production_summary(company, facilities, inventory):
    items = get_next_game_items()
    rates, one_cycle = {}, {}
    cash_rate, profit = 0.0, 0.0
    for facility in facilities:
        recipe = facility["recipe"]
        cycles_per_hour = 3600 / max(1, int(recipe["cycle_seconds"]))
        cash_rate += recipe["operating_cost"] * cycles_per_hour
        raw_cost = 0
        for item_id, quantity in recipe["inputs"].items():
            rates[item_id] = rates.get(item_id, 0) + quantity * cycles_per_hour
            one_cycle[item_id] = one_cycle.get(item_id, 0) + quantity
            raw_cost += quantity * items[item_id]["base_price"] * 1.2
        value = recipe["output_quantity"] * items[recipe["output_item"]]["base_price"] * .8
        profit += (value - raw_cost - recipe["operating_cost"]) * cycles_per_hour
    bounds = [(float(company.cash) / cash_rate * 3600, "cash")] if cash_rate > 0 else []
    for item_id, rate in rates.items():
        if rate > 0:
            bounds.append((inventory.get(item_id, 0) / rate * 3600, item_id))
    limit = min(bounds, default=(None, None), key=lambda value: value[0])
    shortages = [{"item_id": item_id, "name": items[item_id]["name"], "unit": items[item_id]["unit"],
                  "required": round(quantity, 4), "available": round(inventory.get(item_id, 0), 4),
                  "missing": round(max(0, quantity - inventory.get(item_id, 0)), 4)}
                 for item_id, quantity in one_cycle.items() if inventory.get(item_id, 0) + 1e-9 < quantity]
    return {"active": sum(f["status"] == "active" for f in facilities), "total": len(facilities),
            "shortages": shortages, "autonomy_seconds": max(0, int(limit[0])) if limit[0] is not None else None,
            "limiting_item": limit[1], "profit_per_hour": round(profit, 2),
            "operating_cash_per_hour": round(cash_rate, 2),
            "method": "Общий расход всех заводов; выпуск и продажи не включены в запас времени"}
