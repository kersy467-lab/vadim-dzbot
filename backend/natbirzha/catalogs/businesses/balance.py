"""Market-based progression calibration for the live NATBIRZHA 2.0 catalog.

Physical recipe inputs stay intact, including the explicit energy and water
consumption multipliers. The catalog scales output to recover its operating
costs and target return, then scales those recipe inputs with throughput at
every stage. It does not invent extra stock requirements outside the recipes.
"""
from copy import deepcopy

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.inventory import (
    CANONICAL_ITEMS,
)
from backend.natbirzha.services.business_investment import investment_curve, reference_value

MAX_MATERIAL_SAVING = .25
FULL_STAGE_PAYBACK_HOURS = 8.5


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
