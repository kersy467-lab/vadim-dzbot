"""Market-based progression calibration for the live NATBIRZHA 2.0 catalog.

Physical recipe inputs stay intact, including explicit energy and water
consumption multipliers. Shared resource-network inputs, such as AI compute,
are balanced alongside those recipes. The catalog scales output to recover its
operating costs and target return, then scales recipe inputs with throughput at
every stage.
"""
from copy import deepcopy

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.inventory import (
    CANONICAL_ITEMS,
)
from backend.natbirzha.services.business_investment import investment_curve, reference_value

MAX_MATERIAL_SAVING = .25
FULL_STAGE_PAYBACK_HOURS = 8.5
MAX_REFERENCE_EXPENSE_SHARE = .45
STAFF_BEVERAGES = frozenset({"beer", "wine", "aged_spirits"})


def balance_career_catalog(catalog: dict) -> dict:
    result = deepcopy(catalog)
    for spec in result.values():
        if spec["mechanic"] != "resource_production":
            continue

        capital = investment_curve(spec)
        opening_payback = float(spec["target_open_roi_hours"])
        opening_target_profit = capital[1] / opening_payback / (1 - nat_settings.TAX_RATE)
        maintenance = float(spec["base_maintenance_per_hour"])
        core_inputs = dict(spec["inputs_per_hour"])
        # A resource-producing site may have a multi-output by-product recipe.
        # Avoid requiring a company to buy the very item it is producing.
        core_inputs = {
            item: quantity for item, quantity in core_inputs.items()
            if item not in spec["outputs_per_hour"] and quantity > 0
        }
        core_cost = reference_value(core_inputs)
        revenue_for_market_target = core_cost + maintenance + opening_target_profit
        revenue = revenue_for_market_target
        original_revenue = reference_value(spec["outputs_per_hour"])
        if original_revenue <= 0:
            continue

        spec["inputs_per_hour"] = {
            item: round(quantity, 8)
            for item, quantity in core_inputs.items()
            if quantity > 0
        }
        spec["outputs_per_hour"] = {
            item: round(float(quantity) * revenue / original_revenue, 8)
            for item, quantity in spec["outputs_per_hour"].items()
        }

        input_value = reference_value(spec["inputs_per_hour"])
        output_value = reference_value(spec["outputs_per_hour"])
        profiles = {}
        for stage, invested in capital.items():
            normalized_progress = (stage - 1) / max(1, spec["max_stage"] - 1)
            # The upgrade curve accelerates toward an 8.5-hour full-investment
            # payback, while material efficiency improves gradually to 25%.
            progress = normalized_progress ** 2
            payback = opening_payback + (
                FULL_STAGE_PAYBACK_HOURS - opening_payback
            ) * progress
            payback = max(FULL_STAGE_PAYBACK_HOURS, payback)
            efficiency = 1 - MAX_MATERIAL_SAVING * normalized_progress
            target_profit = invested / payback / (1 - nat_settings.TAX_RATE)
            unit_margin = output_value - input_value * efficiency - maintenance * .7
            if unit_margin <= 0:
                continue
            output_factor = (target_profit + maintenance * .3) / unit_margin

            profiles[stage] = {
                "input": output_factor * efficiency,
                "output": output_factor,
                "maintenance": .3 + .7 * output_factor,
                "payback_hours": round(payback, 6),
            }

        spec["stage_rates"] = profiles
        spec["economy_version"] = "market_balance_v2"
        spec["max_material_saving_pct"] = MAX_MATERIAL_SAVING * 100
        spec["full_stage_payback_hours"] = FULL_STAGE_PAYBACK_HOURS
        spec["payback_basis"] = "reference_market_after_tax"
    return result


def cap_career_catalog_expenses(catalog: dict) -> dict:
    """Reduce recipe input throughput where reference expenses exceed revenue cap.

    Output rates and the input recipe mix stay unchanged. Only businesses whose
    reference-priced inputs plus upkeep exceed 45% of gross output are adjusted;
    lower-cost businesses are never made more expensive.
    """
    result = deepcopy(catalog)
    for spec in result.values():
        profiles = spec.get("stage_rates") or {}
        if spec.get("mechanic") != "resource_production" or not profiles:
            continue

        all_inputs = spec.get("inputs_per_hour", {})
        beverage_inputs = {
            item: quantity for item, quantity in all_inputs.items()
            if item in STAFF_BEVERAGES
        }
        recipe_inputs = {
            item: quantity for item, quantity in all_inputs.items()
            if item not in STAFF_BEVERAGES
        }
        beverage_value = reference_value(beverage_inputs)
        recipe_input_value = reference_value(recipe_inputs)
        output_value = reference_value(spec.get("outputs_per_hour", {}))
        if output_value <= 0:
            continue

        capital = investment_curve(spec)
        input_reduction = 1.0
        for raw_stage, profile in profiles.items():
            revenue = output_value * float(profile["output"])
            maintenance = (
                float(spec["base_maintenance_per_hour"])
                * float(profile["maintenance"])
            )
            current_inputs = (
                (recipe_input_value + beverage_value) * float(profile["input"])
            )
            expense_limit = revenue * MAX_REFERENCE_EXPENSE_SHARE
            if current_inputs + maintenance > expense_limit and recipe_input_value > 0:
                affordable_input_cost = max(
                    0.0,
                    expense_limit - maintenance - beverage_value * float(profile["input"]),
                )
                allowed_profile_input = affordable_input_cost / recipe_input_value
                input_reduction = min(
                    input_reduction,
                    allowed_profile_input / max(float(profile["input"]), 1e-12),
                )

        # Apply one efficiency factor to the whole career. This preserves the
        # industry's stage-to-stage input curve instead of making early levels
        # artificially more efficient than later upgrades.
        input_reduction = max(0.0, min(1.0, input_reduction))
        original_input_rates = {
            int(stage): float(profile["input"])
            for stage, profile in profiles.items()
        }
        if input_reduction > 0 and input_reduction < 1:
            for beverage_id, quantity in beverage_inputs.items():
                spec["inputs_per_hour"][beverage_id] = round(
                    float(quantity) / input_reduction,
                    8,
                )
        for raw_stage, profile in profiles.items():
            stage = int(raw_stage)
            profile["input"] = round(float(profile["input"]) * input_reduction, 8)
            revenue = output_value * float(profile["output"])
            maintenance = (
                float(spec["base_maintenance_per_hour"])
                * float(profile["maintenance"])
            )
            actual_expenses = (
                recipe_input_value * float(profile["input"])
                + beverage_value * original_input_rates[stage]
                + maintenance
            )
            after_tax_profit = (
                revenue - actual_expenses
            ) * (1.0 - nat_settings.TAX_RATE)
            if after_tax_profit > 0:
                profile["payback_hours"] = round(
                    capital[stage] / after_tax_profit,
                    6,
                )

        first = profiles.get(1) or profiles.get("1")
        last = profiles.get(int(spec["max_stage"])) or profiles.get(str(spec["max_stage"]))
        spec["max_reference_expense_share_pct"] = MAX_REFERENCE_EXPENSE_SHARE * 100
        spec["expense_cap_input_multiplier"] = round(input_reduction, 8)
        spec["actual_open_roi_hours"] = first["payback_hours"] if first else None
        spec["full_stage_payback_hours"] = last["payback_hours"] if last else None
        spec["economy_version"] = "market_balance_v3"
        spec["payback_basis"] = "reference_market_after_tax_expense_cap"
    return result
