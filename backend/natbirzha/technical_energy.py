"""Shared scaling for live electricity consumption in production catalogs."""

from typing import Any, Mapping

from backend.natbirzha.models.inventory import get_npc_buy_price, get_npc_sell_price


ENERGY_DEMAND_MULTIPLIER = 11


def scale_catalog_energy_inputs(
    specs: Mapping[str, Mapping[str, Any]],
    *,
    input_field: str,
    resource_production_only: bool = False,
) -> dict[str, dict[str, Any]]:
    """Return catalog copies with production electricity inputs multiplied by 11."""
    result: dict[str, dict[str, Any]] = {}
    for spec_id, spec in specs.items():
        scaled = dict(spec)
        if resource_production_only and spec.get("mechanic") != "resource_production":
            result[spec_id] = scaled
            continue

        inputs = dict(spec.get(input_field) or {})
        if "energy" in inputs:
            inputs["energy"] = float(inputs["energy"]) * ENERGY_DEMAND_MULTIPLIER
        scaled[input_field] = inputs

        # Factory recipes are nested in the catalog entry, so scale every
        # alternative recipe as well as the default one before recipe loading.
        if input_field == "inputs" and spec.get("alternate_recipes"):
            alternatives = []
            for recipe in spec["alternate_recipes"]:
                scaled_recipe = dict(recipe)
                recipe_inputs = dict(recipe.get("inputs") or {})
                if "energy" in recipe_inputs:
                    recipe_inputs["energy"] = (
                        float(recipe_inputs["energy"]) * ENERGY_DEMAND_MULTIPLIER
                    )
                scaled_recipe["inputs"] = recipe_inputs
                alternatives.append(scaled_recipe)
            scaled["alternate_recipes"] = alternatives

        result[spec_id] = scaled
    return result


def recalibrate_scaled_energy_outputs(
    specs: Mapping[str, Mapping[str, Any]],
    *,
    multiplier: float = ENERGY_DEMAND_MULTIPLIER,
) -> dict[str, dict[str, Any]]:
    """Preserve calibrated V2 fallback ROI after the electricity cost increase."""
    result = {spec_id: dict(spec) for spec_id, spec in specs.items()}
    factor = max(1.0, float(multiplier))
    for spec in result.values():
        inputs = dict(spec.get("inputs_per_hour") or {})
        outputs = dict(spec.get("outputs_per_hour") or {})
        energy_rate = max(0.0, float(inputs.get("energy", 0.0)))
        if (
            energy_rate <= 0
            or not outputs
            or "target_open_roi_hours" not in spec
            or factor <= 1.0
        ):
            continue

        added_energy_cost = (
            energy_rate * (1.0 - 1.0 / factor) * get_npc_sell_price("energy")
        )
        output_revenue = sum(
            max(0.0, float(quantity)) * get_npc_buy_price(item_id)
            for item_id, quantity in outputs.items()
        )
        if added_energy_cost <= 0 or output_revenue <= 0:
            continue

        output_factor = 1.0 + added_energy_cost / output_revenue
        spec["outputs_per_hour"] = {
            item_id: round(float(quantity) * output_factor, 4)
            for item_id, quantity in outputs.items()
        }
        spec["output_balance_factor"] = round(
            float(spec.get("output_balance_factor", 1.0)) * output_factor,
            6,
        )
    return result

