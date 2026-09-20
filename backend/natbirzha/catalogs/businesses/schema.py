"""Shared, validated shape for server-owned idle business specifications."""

from typing import Any, Mapping


REQUIRED_BUSINESS_SPEC_KEYS = frozenset({
    "id", "name", "tier", "mechanic", "specialization", "max_stage", "slot_weight",
    "open_cost", "base_income_per_hour", "base_maintenance_per_hour", "income_growth",
    "upgrade_cost_growth", "upgrade_time_curve", "inputs_per_hour", "outputs_per_hour",
    "milestones", "upgrade_downtime_mult",
})


def business_spec(
    *,
    business_id: str,
    name: str,
    tier: int,
    mechanic: str,
    specialization: str,
    max_stage: int,
    open_cost: float,
    base_income_per_hour: float,
    base_maintenance_per_hour: float,
    income_growth: float,
    upgrade_cost_growth: float,
    upgrade_time_curve: str,
    inputs_per_hour: Mapping[str, float] | None = None,
    outputs_per_hour: Mapping[str, float] | None = None,
    milestones: Mapping[int, Mapping[str, Any]] | None = None,
    slot_weight: int = 1,
    upgrade_downtime_mult: float = 1.0,
) -> dict[str, Any]:
    return {
        "id": business_id,
        "name": name,
        "tier": tier,
        "mechanic": mechanic,
        "specialization": specialization,
        "max_stage": max_stage,
        "slot_weight": slot_weight,
        "open_cost": open_cost,
        "base_income_per_hour": base_income_per_hour,
        "base_maintenance_per_hour": base_maintenance_per_hour,
        "income_growth": income_growth,
        "upgrade_cost_growth": upgrade_cost_growth,
        "upgrade_time_curve": upgrade_time_curve,
        "inputs_per_hour": dict(inputs_per_hour or {}),
        "outputs_per_hour": dict(outputs_per_hour or {}),
        "milestones": {int(stage): dict(value) for stage, value in (milestones or {}).items()},
        "upgrade_downtime_mult": upgrade_downtime_mult,
    }
