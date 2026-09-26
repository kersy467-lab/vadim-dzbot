"""Single source of truth for NATBIRZHA 2.0 industry progression."""

from typing import Any, Iterable, Mapping, Optional

from .agriculture import AGRICULTURE_BUSINESSES
from .chemistry import CHEMISTRY_BUSINESSES
from .construction import CONSTRUCTION_BUSINESSES
from .energy import ENERGY_BUSINESSES
from .forestry import FORESTRY_BUSINESSES
from .industry import INDUSTRY_BUSINESSES as LEGACY_INDUSTRY_BUSINESSES
from .industry_meta import INDUSTRIES
from .logistics import LOGISTICS_BUSINESSES
from .metallurgy import METALLURGY_BUSINESSES
from .mining import MINING_BUSINESSES
from .oilgas import OIL_GAS_BUSINESSES
from .schema import REQUIRED_BUSINESS_SPEC_KEYS
from .services import SERVICE_BUSINESSES as LEGACY_SERVICE_BUSINESSES
from .starter import STARTER_BUSINESSES as LEGACY_STARTER_BUSINESSES
from backend.natbirzha.technical_water import (
    recalibrate_scaled_water_outputs,
    scale_catalog_water_inputs,
)
from backend.natbirzha.technical_energy import (
    recalibrate_scaled_energy_outputs,
    scale_catalog_energy_inputs,
)
from .technology import TECHNOLOGY_BUSINESSES
from .water import WATER_BUSINESSES
from .balance import balance_career_catalog


LEGACY_BUSINESSES: dict[str, dict[str, Any]] = {
    **LEGACY_STARTER_BUSINESSES,
    **LEGACY_INDUSTRY_BUSINESSES,
    **LEGACY_SERVICE_BUSINESSES,
}
for _legacy in LEGACY_BUSINESSES.values():
    _legacy["legacy_hidden"] = True
LEGACY_BUSINESSES = scale_catalog_water_inputs(
    LEGACY_BUSINESSES,
    input_field="inputs_per_hour",
    resource_production_only=True,
)
LEGACY_BUSINESSES = scale_catalog_energy_inputs(
    LEGACY_BUSINESSES,
    input_field="inputs_per_hour",
    resource_production_only=True,
)

CAREER_BUSINESSES: dict[str, dict[str, Any]] = scale_catalog_water_inputs(
    {
        **MINING_BUSINESSES,
        **AGRICULTURE_BUSINESSES,
        **ENERGY_BUSINESSES,
        **FORESTRY_BUSINESSES,
        **WATER_BUSINESSES,
        **OIL_GAS_BUSINESSES,
        **METALLURGY_BUSINESSES,
        **CHEMISTRY_BUSINESSES,
        **CONSTRUCTION_BUSINESSES,
        **TECHNOLOGY_BUSINESSES,
        **LOGISTICS_BUSINESSES,
    },
    input_field="inputs_per_hour",
    resource_production_only=True,
)
CAREER_BUSINESSES = scale_catalog_energy_inputs(
    CAREER_BUSINESSES,
    input_field="inputs_per_hour",
    resource_production_only=True,
)
CAREER_BUSINESSES = balance_career_catalog(CAREER_BUSINESSES)

BUSINESS_CATALOG: Mapping[str, dict[str, Any]] = {
    **LEGACY_BUSINESSES,
    **CAREER_BUSINESSES,
}


def get_business_spec(business_type: str) -> Optional[dict[str, Any]]:
    return BUSINESS_CATALOG.get((business_type or "").strip().lower())


def visible_business_specs(*, specialization: str | None = None) -> list[dict[str, Any]]:
    values: Iterable[dict[str, Any]] = BUSINESS_CATALOG.values()
    result = [
        spec for spec in values
        if not spec.get("legacy_hidden")
        and (specialization is None or spec["specialization"] == specialization)
    ]
    return sorted(result, key=lambda spec: (spec["specialization"], spec["industry_order"], spec["id"]))


def starter_business_spec(specialization: str) -> Optional[dict[str, Any]]:
    return next(
        (spec for spec in visible_business_specs(specialization=specialization) if spec.get("starter")),
        None,
    )


def validate_business_catalog() -> bool:
    """Fail fast when a server-owned spec cannot be safely used by the engine."""
    seen_ids: set[str] = set()
    starters: dict[str, int] = {}
    for business_type, spec in BUSINESS_CATALOG.items():
        if business_type != spec.get("id") or not REQUIRED_BUSINESS_SPEC_KEYS <= set(spec):
            return False
        if spec["id"] in seen_ids or spec["tier"] < 1 or spec["max_stage"] < 1:
            return False
        if spec["open_cost"] < 0 or spec["base_income_per_hour"] < 0:
            return False
        if spec["upgrade_cost_growth"] <= max(spec["output_growth"], spec["income_growth"]):
            return False
        if spec["slot_weight"] < 1 or not 0 < spec["upgrade_downtime_mult"] <= 1:
            return False
        if spec["company_level_required"] < 1 or spec["territory_required"] < 0:
            return False
        if spec["starter"] and not spec["legacy_hidden"]:
            starters[spec["specialization"]] = starters.get(spec["specialization"], 0) + 1
        seen_ids.add(spec["id"])
    return bool(BUSINESS_CATALOG) and all(starters.get(industry_id) == 1 for industry_id in INDUSTRIES)


__all__ = [
    "BUSINESS_CATALOG",
    "CAREER_BUSINESSES",
    "INDUSTRIES",
    "get_business_spec",
    "starter_business_spec",
    "validate_business_catalog",
    "visible_business_specs",
]
