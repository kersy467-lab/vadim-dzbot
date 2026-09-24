"""Shared scaling for live technical-water production inputs."""

from typing import Any, Mapping

from backend.natbirzha.models.inventory import get_npc_buy_price, get_npc_sell_price


TECHNICAL_WATER_DEMAND_MULTIPLIER = 25 / 1.5
TECHNICAL_WATER_OUTPUT_CALIBRATION_MULTIPLIER = 25


def scale_catalog_water_inputs(
    specs: Mapping[str, Mapping[str, Any]],
    *,
    input_field: str,
    resource_production_only: bool = False,
) -> dict[str, dict[str, Any]]:
    """Return catalog copies with the current technical-water input multiplier."""
    scaled_specs: dict[str, dict[str, Any]] = {}
    for spec_id, spec in specs.items():
        scaled = dict(spec)
        if resource_production_only and spec.get("mechanic") != "resource_production":
            scaled_specs[spec_id] = scaled
            continue

        inputs = dict(spec.get(input_field) or {})
        if "water" in inputs:
            inputs["water"] = float(inputs["water"]) * TECHNICAL_WATER_DEMAND_MULTIPLIER
        scaled[input_field] = inputs
        scaled_specs[spec_id] = scaled
    return scaled_specs


def recalibrate_scaled_water_outputs(
    specs: Mapping[str, Mapping[str, Any]],
    *,
    multiplier: float = TECHNICAL_WATER_OUTPUT_CALIBRATION_MULTIPLIER,
) -> dict[str, dict[str, Any]]:
    """Keep calibrated output rates steady when water input usage is reduced."""
    result = {spec_id: dict(spec) for spec_id, spec in specs.items()}
    factor = max(1.0, float(multiplier))
    for spec in result.values():
        inputs = dict(spec.get("inputs_per_hour") or {})
        outputs = dict(spec.get("outputs_per_hour") or {})
        water_rate = max(0.0, float(inputs.get("water", 0.0)))
        if (
            water_rate <= 0
            or not outputs
            or "target_open_roi_hours" not in spec
            or factor <= 1.0
        ):
            continue

        # Keep output quantities at their previous 25x calibration. A later
        # reduction in water use should lower operating costs, not also shrink
        # the amount of goods a business produces.
        base_water_rate = water_rate / TECHNICAL_WATER_DEMAND_MULTIPLIER
        added_water_cost = base_water_rate * (factor - 1.0) * get_npc_sell_price("water")
        output_revenue = sum(
            max(0.0, float(quantity)) * get_npc_buy_price(item_id)
            for item_id, quantity in outputs.items()
        )
        if added_water_cost <= 0 or output_revenue <= 0:
            continue

        output_factor = 1.0 + added_water_cost / output_revenue
        spec["outputs_per_hour"] = {
            item_id: round(float(quantity) * output_factor, 4)
            for item_id, quantity in outputs.items()
        }
        spec["output_balance_factor"] = round(
            float(spec.get("output_balance_factor", 1.0)) * output_factor,
            6,
        )
    return result
