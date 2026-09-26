"""Deterministic investment costs shared by economic calibration and API quotes."""

from backend.natbirzha.models.inventory import CANONICAL_ITEMS


def reference_value(entries: dict) -> float:
    """Catalog prices only: a temporary crisis must never rewrite physical recipes."""
    return sum(float(quantity) * float(CANONICAL_ITEMS[item]["base_price"])
               for item, quantity in entries.items())


def upgrade_cash_cost(spec: dict, stage: int) -> float:
    current = max(1, int(stage))
    base = max(500.0, float(spec["open_cost"]) * float(spec.get("upgrade_cost_base_multiplier", .25)))
    cost = base * float(spec["upgrade_cost_growth"]) ** (current - 1)
    milestone = spec.get("milestones", {}).get(current + 1, {})
    return round(cost * float(milestone.get("cash_multiplier", 1)), 2)


def investment_curve(spec: dict) -> dict[int, float]:
    capital = float(spec["open_cost"]) + reference_value(spec.get("open_resources", {}))
    curve = {1: capital}
    for stage in range(2, int(spec["max_stage"]) + 1):
        milestone = spec.get("milestones", {}).get(stage, {})
        capital += upgrade_cash_cost(spec, stage - 1) + reference_value(milestone.get("resources", {}))
        curve[stage] = capital
    return curve
