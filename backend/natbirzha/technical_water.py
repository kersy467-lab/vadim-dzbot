"""Shared scaling for live technical-water production inputs."""

from typing import Any, Mapping


TECHNICAL_WATER_DEMAND_MULTIPLIER = 25


def scale_catalog_water_inputs(
    specs: Mapping[str, Mapping[str, Any]],
    *,
    input_field: str,
    resource_production_only: bool = False,
) -> dict[str, dict[str, Any]]:
    """Return catalog copies with live technical-water input rates multiplied by 25."""
    scaled_specs: dict[str, dict[str, Any]] = {}
    for spec_id, spec in specs.items():
        scaled = dict(spec)
        if resource_production_only and spec.get("mechanic") != "resource_production":
            scaled_specs[spec_id] = scaled
            continue

        inputs = dict(spec.get(input_field) or {})
        if "water" in inputs:
            inputs["water"] = float(inputs["water"]) * TECHNICAL_WATER_DEMAND_MULTIPLIER
        scaled[input_field] = inputs
        scaled_specs[spec_id] = scaled
    return scaled_specs
