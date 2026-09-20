"""Single source of truth for NATBIRZHA 2.0 business progression."""

from typing import Any, Mapping, Optional

from .industry import INDUSTRY_BUSINESSES
from .schema import REQUIRED_BUSINESS_SPEC_KEYS
from .services import SERVICE_BUSINESSES
from .starter import STARTER_BUSINESSES


BUSINESS_CATALOG: Mapping[str, dict[str, Any]] = {
    **STARTER_BUSINESSES,
    **INDUSTRY_BUSINESSES,
    **SERVICE_BUSINESSES,
}


def get_business_spec(business_type: str) -> Optional[dict[str, Any]]:
    return BUSINESS_CATALOG.get((business_type or "").strip().lower())


def validate_business_catalog() -> bool:
    """Fail fast when a server-owned spec cannot be safely used by the engine."""
    seen_ids: set[str] = set()
    for business_type, spec in BUSINESS_CATALOG.items():
        if business_type != spec.get("id") or not REQUIRED_BUSINESS_SPEC_KEYS <= set(spec):
            return False
        if spec["id"] in seen_ids or spec["tier"] < 1 or spec["max_stage"] < 1:
            return False
        if spec["open_cost"] < 0 or spec["base_income_per_hour"] < 0:
            return False
        if spec["upgrade_cost_growth"] <= spec["income_growth"]:
            return False
        if spec["slot_weight"] < 1 or not 0 < spec["upgrade_downtime_mult"] <= 1:
            return False
        seen_ids.add(spec["id"])
    return bool(BUSINESS_CATALOG)


__all__ = ["BUSINESS_CATALOG", "get_business_spec", "validate_business_catalog"]
