"""Estimate how long available warehouse stock supports V2 production."""

import math
from collections import defaultdict
from typing import Iterable, Mapping, Any

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.business_rates import resource_business_rates

_CONSUMING_STATUSES = frozenset({"ACTIVE", "UPGRADING", "PAUSED_SUPPLY"})


def _nonnegative_finite(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, number) if math.isfinite(number) else 0.0


def build_business_inventory_runway(
    businesses: Iterable[Any], available_inventory: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the aggregate stock runway for active and supply-paused V2 businesses.

    Resource input rates use the same catalog and stage/condition modifiers as
    business settlement. Supply-paused businesses are included because they
    resume consuming when stock returns. Reserved inventory is excluded by the
    caller, which supplies existing ``available_quantity`` values.
    """
    consumption: dict[str, float] = defaultdict(float)
    consuming_count = 0

    for business in businesses:
        status = str(getattr(business, "status", "")).upper()
        if status not in _CONSUMING_STATUSES:
            continue
        spec = get_business_spec(getattr(business, "business_type", ""))
        if (
            spec is None
            or spec.get("legacy_hidden")
            or spec.get("mechanic") != "resource_production"
        ):
            continue

        base_inputs = spec.get("inputs_per_hour") or {}
        if not base_inputs:
            continue
        rates = resource_business_rates(
            business, spec, upgrading=status == "UPGRADING"
        )
        multiplier = _nonnegative_finite(rates.input_multiplier)
        business_rates = {
            item_id: _nonnegative_finite(base_rate) * multiplier
            for item_id, base_rate in base_inputs.items()
        }
        business_rates = {
            item_id: rate for item_id, rate in business_rates.items() if rate > 0
        }
        if not business_rates:
            continue
        consuming_count += 1
        for item_id, rate in business_rates.items():
            consumption[item_id] += rate

    if not consuming_count:
        return {
            "status": "NO_CONSUMERS",
            "hours": None,
            "active_consuming_business_count": 0,
            "consumption_per_hour": {},
            "limiting_resources": [],
        }

    stock_by_item = {
        item_id: _nonnegative_finite(available_inventory.get(item_id, 0.0))
        for item_id in consumption
    }
    hours_by_item = {
        item_id: stock_by_item[item_id] / rate
        for item_id, rate in consumption.items()
        if rate > 0
    }
    hours = min(hours_by_item.values(), default=0.0)
    limiting_resources = []
    for item_id in sorted(hours_by_item):
        if not math.isclose(hours_by_item[item_id], hours, rel_tol=1e-9, abs_tol=1e-9):
            continue
        item = CANONICAL_ITEMS.get(item_id, {})
        limiting_resources.append({
            "item_id": item_id,
            "name": str(item.get("name") or item_id),
            "unit": str(item.get("unit") or "ед."),
            "available_quantity": round(stock_by_item[item_id], 6),
            "consumption_per_hour": round(consumption[item_id], 6),
        })

    return {
        "status": "OUT_OF_STOCK" if hours <= 0 else "RUNWAY",
        "hours": round(hours, 6),
        "active_consuming_business_count": consuming_count,
        "consumption_per_hour": {
            item_id: round(rate, 6) for item_id, rate in sorted(consumption.items())
        },
        "limiting_resources": limiting_resources,
    }


__all__ = ["build_business_inventory_runway"]
