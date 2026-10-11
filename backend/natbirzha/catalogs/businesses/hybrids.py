"""Production recipes that combine career-stage pairs in every industry."""

from copy import deepcopy
from typing import Any

from backend.natbirzha.models.inventory import CANONICAL_ITEMS

from .career import career_business


HYBRID_SOURCE_PAIR_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "miner": (
        ("coal_open_pit", "iron_quarry"),
        ("silver_mine", "gold_mine"),
        ("lithium_quarry_v2", "cobalt_mine_v2"),
    ),
    "agrarian": (
        ("grain_farm_v2", "dairy_farm_v2"),
        ("poultry_farm_v2", "vegetable_farm_v2"),
        ("food_processing_v2", "agro_holding_v2"),
    ),
    "power_engineer": (
        ("diesel_power_station", "small_gas_chp"),
        ("wind_park_v2", "solar_park_v2"),
        ("combined_tpp", "nuclear_station_v2"),
    ),
    "water": (
        ("artesian_well", "pump_station_v2"),
        ("industrial_waterworks", "water_reservoir"),
        ("desalination_complex", "ultrapure_water_plant"),
    ),
    "oilman": (
        ("small_oil_well_v2", "gas_well_v2"),
        ("refinery_v2", "diesel_complex_v2"),
        ("large_gas_field", "offshore_platform_v2"),
    ),
    "metallurgist": (
        ("pig_iron_shop", "steel_plant_v2"),
        ("copper_smelter_v2", "aluminum_plant_v2"),
        ("high_strength_materials", "titanium_complex"),
    ),
    "chemist": (
        ("fertilizer_factory_v2", "reagent_factory_v2"),
        ("polymer_factory_v2", "lubricant_factory_v2"),
        ("high_purity_reagents", "chemical_concern_v2"),
    ),
    "construction": (
        ("logging_site_v2", "lumber_mill_v2"),
        ("cement_factory", "concrete_factory"),
        ("industrial_contractor", "infrastructure_holding"),
    ),
    "ai_data": (
        ("ai_compute_node", "ml_training_center"),
        ("cloud_ai_center", "machine_vision_lab"),
        ("foundation_model_cluster", "national_ai_supercomputer"),
    ),
    "technoprom": (
        ("electronics_workshop", "electrical_factory"),
        ("robotics_factory_v2", "battery_system_factory"),
        ("ai_research_center", "technology_megacorp"),
    ),
    "logistics": (
        ("courier_service_v2", "trucking_company_v2"),
        ("rail_operator_v2", "container_terminal_v2"),
        ("seaport_v2", "air_freight_network"),
    ),
    "brewery": (
        ("craft_brewery", "regional_brewery"),
        ("regional_winery", "sparkling_winery"),
        ("aged_cognac_house", "cognac_export_complex"),
    ),
}

# Preserve the original recipe mapping for callers that only need one example
# pair per industry. The full selectable catalog is HYBRID_SOURCE_PAIR_OPTIONS.
HYBRID_SOURCE_PAIRS: dict[str, tuple[str, str]] = {
    specialization: pairs[0]
    for specialization, pairs in HYBRID_SOURCE_PAIR_OPTIONS.items()
}

_FORMATION_RESOURCES: dict[str, dict[str, float]] = {
    "miner": {"steel": 2.0, "energy": 5.0},
    "agrarian": {"fertilizer": 2.0, "water": 2.0},
    "power_engineer": {"steel": 2.0, "fuel_diesel": 2.0},
    "water": {"energy": 2.0, "steel": 1.0},
    "oilman": {"steel": 3.0, "energy": 2.0},
    "metallurgist": {"iron_ore": 2.0, "coal": 2.0},
    "chemist": {"basic_chem": 2.0, "energy": 2.0},
    "construction": {"cement": 2.0, "steel": 2.0},
    "ai_data": {"electronics": 2.0, "energy": 1.0},
    "technoprom": {"copper": 1.0, "components": 1.0},
    "logistics": {"fuel_diesel": 2.0, "logistics_capacity": 1.0},
    "brewery": {"grain": 2.0, "hops": 1.0, "water": 2.0},
}

INPUT_REDUCTION_RATIO = 0.08
OUTPUT_BONUS_RATIO = 0.08
MAINTENANCE_REDUCTION_RATIO = 0.15
ADDITIONAL_CAPITAL_RATIO = 0.50
SALE_REFUND_RATIO = 0.40

_MILESTONES = (
    "Объединение производственных линий",
    "Снижение потерь сырья",
    "Цифровое управление комплексом",
    "Автоматизация смен",
    "Единый отраслевой холдинг",
)


def _sum_rates(specs: list[dict[str, Any]], field: str, factor: float = 1.0) -> dict[str, float]:
    totals: dict[str, float] = {}
    for spec in specs:
        for item_id, quantity in spec[field].items():
            totals[item_id] = totals.get(item_id, 0.0) + float(quantity)
    return {
        item_id: round(quantity * factor, 8)
        for item_id, quantity in totals.items()
        if quantity > 0
    }


def _market_value(entries: dict[str, float]) -> float:
    return sum(
        float(quantity) * float(CANONICAL_ITEMS[item_id]["base_price"])
        for item_id, quantity in entries.items()
    )


def _stage_profile(spec: dict[str, Any], stage: int) -> dict[str, float]:
    profiles = spec.get("stage_rates") or {}
    return profiles.get(stage) or profiles.get(str(stage)) or {
        "input": 1.0,
        "output": 1.0,
        "maintenance": 1.0,
        "payback_hours": 0.0,
    }


def _combined_stage_rates(
    source_specs: list[dict[str, Any]],
    inputs: dict[str, float],
    outputs: dict[str, float],
    maintenance: float,
) -> dict[int, dict[str, float]]:
    """Keep a hybrid's stage throughput equal to its two source lines combined."""
    output_base_value = _market_value(outputs)
    input_base_value = _market_value(inputs)
    source_output_values = [_market_value(spec["outputs_per_hour"]) for spec in source_specs]
    source_input_values = [
        _market_value({item: quantity for item, quantity in spec["inputs_per_hour"].items() if item in inputs})
        for spec in source_specs
    ]
    source_maintenance_values = [float(spec["base_maintenance_per_hour"]) for spec in source_specs]
    source_total_output = sum(source_output_values)
    profiles: dict[int, dict[str, float]] = {}

    for stage in range(1, 51):
        rates = [_stage_profile(spec, stage) for spec in source_specs]
        combined_output = sum(
            source_output_values[index] * float(rates[index]["output"])
            for index in range(len(source_specs))
        )
        combined_input = sum(
            source_input_values[index] * float(rates[index]["input"])
            for index in range(len(source_specs))
        )
        combined_maintenance = sum(
            source_maintenance_values[index] * float(rates[index]["maintenance"])
            for index in range(len(source_specs))
        )
        profiles[stage] = {
            "input": round((1 - INPUT_REDUCTION_RATIO) * combined_input / input_base_value, 8)
            if input_base_value > 0 else 1.0,
            "output": round((1 + OUTPUT_BONUS_RATIO) * combined_output / output_base_value, 8)
            if output_base_value > 0 else 1.0,
            "maintenance": round((1 - MAINTENANCE_REDUCTION_RATIO) * combined_maintenance / maintenance, 8)
            if maintenance > 0 else 1.0,
            "payback_hours": round(
                sum(
                    source_output_values[index] * float(rates[index].get("payback_hours", 0.0))
                    for index in range(len(source_specs))
                ) / source_total_output,
                6,
            ) if source_total_output > 0 else 0.0,
        }
    return profiles


def build_hybrid_catalog(
    source_catalog: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build three balanced production recipes for each specialization.

    Each hybrid runs through the same hourly settlement as ordinary career
    businesses. It combines the source recipes, uses 8% fewer listed inputs,
    raises combined output throughput by 8%, and keeps 15% lower upkeep than
    the two plants' combined base maintenance. All consumed/produced items are
    existing catalog resources; this builder never initializes inventory.
    """
    if set(HYBRID_SOURCE_PAIR_OPTIONS) != set(_FORMATION_RESOURCES):
        raise RuntimeError("Для каждого гибрида требуются пара предприятий и ресурсы открытия")

    businesses: dict[str, dict[str, Any]] = {}
    recipes: dict[str, dict[str, Any]] = {}
    for specialization, source_pairs in HYBRID_SOURCE_PAIR_OPTIONS.items():
        for option_index, source_types in enumerate(source_pairs):
            source_specs = [source_catalog.get(business_type) for business_type in source_types]
            if any(spec is None or spec.get("legacy_hidden") for spec in source_specs):
                raise RuntimeError(f"В активном каталоге отсутствует пара гибрида: {specialization} {source_types}")
            if any(spec["specialization"] != specialization for spec in source_specs):
                raise RuntimeError(f"Пара гибрида не совпадает с отраслью {specialization}")

            resources = deepcopy(_FORMATION_RESOURCES[specialization])
            if any(item_id not in CANONICAL_ITEMS or quantity <= 0 for item_id, quantity in resources.items()):
                raise RuntimeError(f"Гибрид {specialization} ссылается на неизвестный ресурс открытия")
            extra_capital = max(
                100.0,
                round(sum(float(spec["open_cost"]) for spec in source_specs) * ADDITIONAL_CAPITAL_RATIO, 2),
            )
            inputs = _sum_rates(source_specs, "inputs_per_hour", 1 - INPUT_REDUCTION_RATIO)
            outputs = _sum_rates(source_specs, "outputs_per_hour", 1 + OUTPUT_BONUS_RATIO)
            # A combined plant can internally supply an input produced by one
            # of its own lines, matching the ordinary career balance rules.
            inputs = {item: quantity for item, quantity in inputs.items() if item not in outputs}
            source_items = tuple(dict.fromkeys(
                item_id
                for spec in source_specs
                for item_id in (*spec["inputs_per_hour"], *spec["outputs_per_hour"])
            ))
            option_suffix = "" if option_index == 0 else f"_{option_index + 1}"
            business_id = f"hybrid_{specialization}{option_suffix}"
            name = f"Гибридный комплекс: {source_specs[0]['name']} + {source_specs[1]['name']}"
            maintenance = round(
                sum(float(spec["base_maintenance_per_hour"]) for spec in source_specs)
                * (1 - MAINTENANCE_REDUCTION_RATIO),
                4,
            )
            spec = career_business(
                business_id=business_id,
                name=name,
                icon="🏭",
                specialization=specialization,
                order=option_index + 1,
                open_cost=extra_capital,
                level_required=1,
                inputs=inputs,
                outputs=outputs,
                milestones=_MILESTONES,
                milestone_resources=source_items,
                description=(
                    "Объединяет две действующие производственные линии: выпуск на 8% выше, "
                    "расход ресурсов на 8% ниже, обслуживание на 15% дешевле."
                ),
                prerequisites={source_types[0]: 1, source_types[1]: 1},
                territory_required=0,
                open_resources={},
                mechanic="resource_production",
                base_income_per_hour=0.0,
                tags=("hybrid", "combined-production"),
                starter=False,
                unique=False,
            )
            # career_business calibrates standalone plants for their opening
            # price. A hybrid already contains both calibrated source recipes;
            # applying that calibration again discards most of their output.
            spec["inputs_per_hour"] = inputs
            spec["outputs_per_hour"] = outputs
            spec["base_maintenance_per_hour"] = maintenance
            spec["max_stage"] = 50
            spec["stage_rates"] = _combined_stage_rates(
                source_specs, inputs, outputs, maintenance
            )
            spec["economy_version"] = "hybrid_combined_production_v1"
            spec["hybrid_only"] = True
            spec["hybrid_source_business_types"] = source_types
            spec["input_reduction_ratio"] = INPUT_REDUCTION_RATIO
            spec["output_bonus_ratio"] = OUTPUT_BONUS_RATIO
            spec["maintenance_reduction_ratio"] = MAINTENANCE_REDUCTION_RATIO
            spec["slot_weight"] = 1
            spec["industry_order"] = 1 + option_index
            businesses[business_id] = spec
            recipes[business_id] = {
                "id": business_id,
                "business_type": business_id,
                "specialization": specialization,
                "source_business_types": source_types,
                "minimum_source_stage": 1,
                "source_slot_weight": 1,
                "hybrid_slot_weight": 1,
                "max_stage": int(spec["max_stage"]),
                "additional_capital_cost": extra_capital,
                "resource_requirements": resources,
                "input_reduction_ratio": INPUT_REDUCTION_RATIO,
                "output_bonus_ratio": OUTPUT_BONUS_RATIO,
                "maintenance_reduction_ratio": MAINTENANCE_REDUCTION_RATIO,
                "sale_refund_ratio": SALE_REFUND_RATIO,
            }

    return businesses, recipes


__all__ = ["HYBRID_SOURCE_PAIRS", "HYBRID_SOURCE_PAIR_OPTIONS", "build_hybrid_catalog"]
