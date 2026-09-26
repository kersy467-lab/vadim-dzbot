"""Production recipes that combine two existing enterprises per industry."""

from copy import deepcopy
from typing import Any

from backend.natbirzha.models.inventory import CANONICAL_ITEMS

from .career import career_business


HYBRID_SOURCE_PAIRS: dict[str, tuple[str, str]] = {
    "miner": ("coal_open_pit", "iron_quarry"),
    "agrarian": ("grain_farm_v2", "dairy_farm_v2"),
    "power_engineer": ("diesel_power_station", "small_gas_chp"),
    "water": ("artesian_well", "pump_station_v2"),
    "oilman": ("small_oil_well_v2", "gas_well_v2"),
    "metallurgist": ("pig_iron_shop", "steel_plant_v2"),
    "chemist": ("fertilizer_factory_v2", "reagent_factory_v2"),
    "construction": ("logging_site_v2", "lumber_mill_v2"),
    "forester": ("forest_management_v2", "sawmill_v2"),
    "technoprom": ("electronics_workshop", "electrical_factory"),
    "logistics": ("courier_service_v2", "trucking_company_v2"),
    "brewery": ("craft_brewery", "regional_brewery"),
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
    "forester": {"wood_raw": 2.0, "energy": 1.0},
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


def build_hybrid_catalog(
    source_catalog: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build a balanced production spec and open recipe for each sector.

    Each hybrid runs through the same hourly settlement as ordinary career
    businesses. It combines the source recipes, uses 8% fewer listed inputs,
    raises combined output throughput by 8%, and keeps 15% lower upkeep than
    the two plants' combined base maintenance. All consumed/produced items are
    existing catalog resources; this builder never initializes inventory.
    """
    if set(HYBRID_SOURCE_PAIRS) != set(_FORMATION_RESOURCES):
        raise RuntimeError("Для каждого гибрида требуются пара предприятий и ресурсы открытия")

    businesses: dict[str, dict[str, Any]] = {}
    recipes: dict[str, dict[str, Any]] = {}
    for specialization, source_types in HYBRID_SOURCE_PAIRS.items():
        source_specs = [source_catalog.get(business_type) for business_type in source_types]
        if any(spec is None or spec.get("legacy_hidden") for spec in source_specs):
            raise RuntimeError(f"В активном каталоге отсутствует пара гибрида: {specialization}")
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
        source_items = tuple(dict.fromkeys(
            item_id
            for spec in source_specs
            for item_id in (*spec["inputs_per_hour"], *spec["outputs_per_hour"])
        ))
        business_id = f"hybrid_{specialization}"
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
            order=1,
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
        spec["base_maintenance_per_hour"] = maintenance
        spec["hybrid_only"] = True
        spec["hybrid_source_business_types"] = source_types
        spec["input_reduction_ratio"] = INPUT_REDUCTION_RATIO
        spec["output_bonus_ratio"] = OUTPUT_BONUS_RATIO
        spec["maintenance_reduction_ratio"] = MAINTENANCE_REDUCTION_RATIO
        spec["slot_weight"] = 1
        spec["industry_order"] = 1
        businesses[business_id] = spec
        recipes[business_id] = {
            "id": business_id,
            "business_type": business_id,
            "specialization": specialization,
            "source_business_types": source_types,
            "minimum_source_stage": 1,
            "source_slot_weight": 1,
            "hybrid_slot_weight": 1,
            "additional_capital_cost": extra_capital,
            "resource_requirements": resources,
            "input_reduction_ratio": INPUT_REDUCTION_RATIO,
            "output_bonus_ratio": OUTPUT_BONUS_RATIO,
            "maintenance_reduction_ratio": MAINTENANCE_REDUCTION_RATIO,
            "sale_refund_ratio": SALE_REFUND_RATIO,
        }

    return businesses, recipes


__all__ = ["HYBRID_SOURCE_PAIRS", "build_hybrid_catalog"]
