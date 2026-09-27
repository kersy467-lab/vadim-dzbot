"""Shared consumption profiles that connect each industry to AI compute demand."""


AI_COMPUTE_DEMAND_BY_ORDER = {
    1: 1.0,
    2: 0.55,
    3: 0.40,
    4: 0.32,
    5: 0.28,
    6: 0.45,
    7: 1.5,
    8: 3.0,
    9: 6.5,
    10: 11.0,
    11: 18.0,
    12: 28.0,
}


def add_ai_compute_demand(catalog: dict[str, dict]) -> dict[str, dict]:
    """Give all non-AI industry enterprises a low-to-high compute demand curve.

    Starter plants make demand immediately visible. Mid-career lines use less
    compute per plant; high-tier automation and data processing use much more.
    """
    for spec in catalog.values():
        if spec.get("specialization") == "ai_data" or spec.get("legacy_hidden"):
            continue
        if spec.get("mechanic") != "resource_production":
            continue
        order = max(1, int(spec.get("industry_order", 1)))
        amount = AI_COMPUTE_DEMAND_BY_ORDER.get(order, 28.0)
        inputs = dict(spec.get("inputs_per_hour", {}))
        inputs["ai_compute"] = amount
        spec["inputs_per_hour"] = inputs
        spec.setdefault("resource_network_inputs", {})["ai_compute"] = amount
    return catalog


__all__ = ["AI_COMPUTE_DEMAND_BY_ORDER", "add_ai_compute_demand"]
