"""Shared scaling for live electricity consumption in production catalogs."""

from typing import Any, Mapping

from backend.natbirzha.models.inventory import get_npc_buy_price, get_npc_sell_price


ENERGY_DEMAND_MULTIPLIER = 11
INDUSTRY_ENERGY_USAGE_FACTOR = 0.75
AI_ENERGY_USAGE_FACTOR = 0.90
AI_TECHNICAL_WATER_USAGE_FACTOR = 1.13
AI_WATER_INPUTS = frozenset({"water", "clean_water", "ultrapure_water"})


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


def apply_industry_resource_usage_adjustments(
    specs: Mapping[str, Mapping[str, Any]],
    *,
    input_field: str,
    resource_production_only: bool = False,
) -> dict[str, dict[str, Any]]:
    """Apply final per-industry utility adjustments after catalog calibration.

    These factors compose with the catalog's existing technical-energy and
    technical-water multipliers without changing production multipliers or outputs.
    """
    result: dict[str, dict[str, Any]] = {}
    for spec_id, spec in specs.items():
        adjusted = dict(spec)
        if resource_production_only and spec.get("mechanic") != "resource_production":
            result[spec_id] = adjusted
            continue

        is_ai = spec.get("specialization") == "ai_data"

        def adjust_inputs(raw_inputs: Mapping[str, Any] | None) -> dict[str, Any]:
            inputs = dict(raw_inputs or {})
            if "energy" in inputs:
                energy_factor = AI_ENERGY_USAGE_FACTOR if is_ai else INDUSTRY_ENERGY_USAGE_FACTOR
                inputs["energy"] = round(float(inputs["energy"]) * energy_factor, 8)
            if is_ai:
                for item_id in AI_WATER_INPUTS & inputs.keys():
                    inputs[item_id] = round(
                        float(inputs[item_id]) * AI_TECHNICAL_WATER_USAGE_FACTOR,
                        8,
                    )
            return inputs

        adjusted[input_field] = adjust_inputs(spec.get(input_field))
        if input_field == "inputs" and spec.get("alternate_recipes"):
            alternatives = []
            for recipe in spec["alternate_recipes"]:
                adjusted_recipe = dict(recipe)
                adjusted_recipe["inputs"] = adjust_inputs(recipe.get("inputs"))
                alternatives.append(adjusted_recipe)
            adjusted["alternate_recipes"] = alternatives
        if input_field == "inputs_per_hour":
            _refresh_resource_payback_metadata(adjusted)
        result[spec_id] = adjusted
    return result


def _refresh_resource_payback_metadata(spec: dict[str, Any]) -> None:
    """Revalue V2 ROI metadata after final input rates without changing rates."""
    profiles = spec.get("stage_rates") or {}
    if spec.get("mechanic") != "resource_production" or not profiles:
        return

    from backend.natbirzha.config import nat_settings
    from backend.natbirzha.services.business_investment import (
        investment_curve,
        reference_value,
    )

    capital = investment_curve(spec)
    output_value = reference_value(spec.get("outputs_per_hour", {}))
    input_value = reference_value(spec.get("inputs_per_hour", {}))
    tax_multiplier = 1.0 - float(nat_settings.TAX_RATE)
    for raw_stage, profile in profiles.items():
        stage = int(raw_stage)
        if stage not in capital:
            continue
        revenue = output_value * float(profile["output"])
        expenses = (
            input_value * float(profile["input"])
            + float(spec["base_maintenance_per_hour"]) * float(profile["maintenance"])
        )
        after_tax_profit = (revenue - expenses) * tax_multiplier
        if after_tax_profit > 0:
            profile["payback_hours"] = round(capital[stage] / after_tax_profit, 6)

    first = profiles.get(1) or profiles.get("1")
    last_stage = int(spec["max_stage"])
    last = profiles.get(last_stage) or profiles.get(str(last_stage))
    spec["actual_open_roi_hours"] = first["payback_hours"] if first else None
    spec["full_stage_payback_hours"] = last["payback_hours"] if last else None


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

