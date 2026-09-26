"""Small beverage supplies consumed by employees across industry careers."""

from collections.abc import Mapping

from backend.natbirzha.models.inventory import CANONICAL_ITEMS


_EMPLOYEE_BEVERAGE_BY_ORDER = (
    (3, "beer"),
    (8, "wine"),
    (50, "aged_spirits"),
)
_OUTPUT_VALUE_SHARE = 0.01


def add_employee_beverage_input(
    inputs: Mapping[str, float],
    outputs: Mapping[str, float],
    *,
    specialization: str,
    order: int,
    reference_output_revenue: float | None = None,
    input_rate_multiplier: float = 1.0,
) -> dict[str, float]:
    """Add a small, value-capped beverage input to a non-brewery business.

    Early businesses consume beer, mid-career businesses consume wine, and
    advanced businesses consume elite aged spirits. The rate stays at or below
    one percent of the calibrated output revenue. `reference_output_revenue`
    is the value after the catalog's first-stage rate multipliers are applied.
    """
    result = {str(item): float(quantity) for item, quantity in inputs.items()}
    if str(specialization).strip().lower() == "brewery":
        return result

    business_order = max(1, int(order))
    beverage_id = next(
        item_id
        for maximum_order, item_id in _EMPLOYEE_BEVERAGE_BY_ORDER
        if business_order <= maximum_order
    )
    output_value = (
        max(0.0, float(reference_output_revenue))
        if reference_output_revenue is not None
        else sum(
            max(0.0, float(quantity)) * float(CANONICAL_ITEMS[item_id]["base_price"])
            for item_id, quantity in outputs.items()
        )
    )
    unit_cost = float(CANONICAL_ITEMS[beverage_id]["base_price"])
    if output_value <= 0 or unit_cost <= 0:
        return result

    input_multiplier = max(0.0, float(input_rate_multiplier))
    if input_multiplier <= 0:
        return result
    beverage_budget = output_value * _OUTPUT_VALUE_SHARE
    hourly_quantity = beverage_budget / (unit_cost * input_multiplier)
    result[beverage_id] = result.get(beverage_id, 0.0) + hourly_quantity
    return result


def add_employee_beverages_to_catalog(catalog: Mapping[str, dict]) -> dict[str, dict]:
    """Add worker beverage demand after market balancing, preserving its rates.

    Career stage profiles apply separate input/output multipliers. The quantity
    is therefore calibrated against the first-stage cash value after both
    multipliers, instead of raw recipe quantities before catalog balancing.
    """
    result = dict(catalog)
    for business_id, original_spec in catalog.items():
        spec = dict(original_spec)
        stage_one = (spec.get("stage_rates") or {}).get(1, {})
        input_multiplier = float(stage_one.get("input", 1.0))
        output_multiplier = float(stage_one.get("output", 1.0))
        output_revenue = sum(
            max(0.0, float(quantity))
            * output_multiplier
            * float(CANONICAL_ITEMS[item_id]["base_price"])
            for item_id, quantity in spec.get("outputs_per_hour", {}).items()
        )
        spec["inputs_per_hour"] = add_employee_beverage_input(
            spec.get("inputs_per_hour", {}),
            spec.get("outputs_per_hour", {}),
            specialization=str(spec.get("specialization", "")),
            order=int(spec.get("industry_order", 1)),
            reference_output_revenue=output_revenue,
            input_rate_multiplier=input_multiplier,
        )
        output_value = sum(
            max(0.0, float(quantity))
            * float(CANONICAL_ITEMS[item_id]["base_price"])
            for item_id, quantity in spec.get("outputs_per_hour", {}).items()
        )
        beverage_cost = sum(
            max(0.0, float(quantity))
            * float(CANONICAL_ITEMS[item_id]["base_price"])
            for item_id, quantity in spec["inputs_per_hour"].items()
            if item_id in {"beer", "wine", "aged_spirits"}
        )
        if (
            str(spec.get("specialization", "")).strip().lower() != "brewery"
            and output_value > 0
            and beverage_cost > 0
        ):
            # The catalog's payback calculation values inputs and outputs at
            # canonical reference prices. Add matching output per stage so
            # employee supplies don't silently worsen the agreed ROI curve.
            for rates in (spec.get("stage_rates") or {}).values():
                rates["output"] += beverage_cost * float(rates["input"]) / output_value
        result[business_id] = spec
    return result


__all__ = ["add_employee_beverage_input", "add_employee_beverages_to_catalog"]
