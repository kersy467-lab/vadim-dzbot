"""Server-owned recipes for factories co-owned by two industries."""

from statistics import median

from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.business_investment import reference_value


INDUSTRY_PARTNERSHIPS = (
    ("miner", "logistics"),
    ("miner", "metallurgist"),
    ("metallurgist", "chemist"),
    ("chemist", "oilman"),
    ("oilman", "technoprom"),
    ("technoprom", "power_engineer"),
    ("power_engineer", "water"),
    ("water", "agrarian"),
    ("agrarian", "brewery"),
    ("brewery", "forester"),
    ("forester", "construction"),
    ("construction", "logistics"),
)

INDUSTRY_JOINT_GOODS = {
    "miner": "iron_ore",
    "agrarian": "grain",
    "power_engineer": "energy",
    "water": "water",
    "oilman": "oil_crude",
    "metallurgist": "steel",
    "chemist": "fertilizer",
    "construction": "concrete",
    "forester": "lumber",
    "technoprom": "components",
    "logistics": "logistics_capacity",
    "brewery": "beer",
}

_LEVEL_STAGES = (1, 10, 25, 50)
_OUTPUT_SHARE_OF_LOWER_BENCHMARK = 0.70
_INVESTMENT_PAYBACK_HOURS = 15.0


def _industry_benchmark(catalog: dict, industry: str, target_stage: int) -> float:
    values: list[float] = []
    for spec in catalog.values():
        if spec.get("specialization") != industry or spec.get("mechanic") != "resource_production":
            continue
        if spec.get("legacy_hidden") or spec.get("hybrid_only"):
            continue
        output_value = reference_value(spec.get("outputs_per_hour", {}))
        if output_value <= 0:
            continue
        profiles = spec.get("stage_rates", {})
        available_stages = sorted(int(stage) for stage in profiles)
        profile_stage = min(target_stage, int(spec.get("max_stage", target_stage)))
        profile_stage = max((stage for stage in available_stages if stage <= profile_stage), default=1)
        output_multiplier = float(profiles.get(profile_stage, {}).get("output", 1.0))
        values.append(output_value * output_multiplier)
    return float(median(values)) if values else 0.0


def build_joint_factory_catalog(career_catalog: dict) -> dict[str, dict]:
    """Build four production stages and bilateral build costs for each pairing.

    Each partner receives half of both output streams. The combined output is
    calibrated so that each owner's hourly goods are worth 70% of the weaker
    partner-industry benchmark at the matching ordinary factory stage.
    Construction/upgrades target a 15-hour resource-value payback per owner.
    """
    recipes: dict[str, dict] = {}
    for industry_a, industry_b in INDUSTRY_PARTNERSHIPS:
        recipe_id = f"joint_{industry_a}_{industry_b}"
        item_a, item_b = INDUSTRY_JOINT_GOODS[industry_a], INDUSTRY_JOINT_GOODS[industry_b]
        base_prices = {
            item: float(CANONICAL_ITEMS[item]["base_price"])
            for item in (item_a, item_b)
        }
        levels: list[dict] = []
        previous_owner_value = 0.0
        for level_number, target_stage in enumerate(_LEVEL_STAGES, start=1):
            benchmarks = {
                industry: _industry_benchmark(career_catalog, industry, target_stage)
                for industry in (industry_a, industry_b)
            }
            weaker_benchmark = min(benchmarks.values())
            owner_share_value = round(weaker_benchmark * _OUTPUT_SHARE_OF_LOWER_BENCHMARK, 6)
            per_output_stream_value = owner_share_value
            outputs_per_hour = {
                item_a: round(per_output_stream_value / base_prices[item_a], 8),
                item_b: round(per_output_stream_value / base_prices[item_b], 8),
            }
            incremental_value = owner_share_value if level_number == 1 else max(
                0.0, owner_share_value - previous_owner_value
            )
            contribution_budget = max(100.0, incremental_value * _INVESTMENT_PAYBACK_HOURS / 2)
            contributions = {}
            for industry in (industry_a, industry_b):
                resource = INDUSTRY_JOINT_GOODS[industry]
                resource_price = float(CANONICAL_ITEMS[resource]["base_price"])
                contributions[industry] = {
                    "cash": round(contribution_budget, 2),
                    "resources": {
                        resource: round(contribution_budget / resource_price, 6),
                    },
                }
            levels.append({
                "level": level_number,
                "ordinary_factory_stage": target_stage,
                "outputs_per_hour": outputs_per_hour,
                "inputs_per_hour": {},
                "maintenance_per_hour": 0.0,
                "industry_benchmarks": benchmarks,
                "owner_share_reference_value": owner_share_value,
                "contributions": contributions,
            })
            previous_owner_value = owner_share_value

        recipes[recipe_id] = {
            "id": recipe_id,
            "specializations": (industry_a, industry_b),
            "output_items": {industry_a: item_a, industry_b: item_b},
            "levels": levels,
        }
    return recipes


__all__ = ["INDUSTRY_JOINT_GOODS", "INDUSTRY_PARTNERSHIPS", "build_joint_factory_catalog"]
