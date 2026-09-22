"""Validated server-owned shapes for NATBIRZHA 2.0 business progression."""

from typing import Any, Mapping, Sequence


REQUIRED_BUSINESS_SPEC_KEYS = frozenset({
    "id", "name", "description", "icon", "tier", "mechanic", "specialization",
    "max_stage", "slot_weight", "open_cost", "base_income_per_hour",
    "base_maintenance_per_hour", "income_growth", "input_growth", "output_growth",
    "upgrade_cost_growth", "upgrade_time_curve", "inputs_per_hour", "outputs_per_hour",
    "milestones", "upgrade_downtime_mult", "company_level_required", "prerequisites",
    "territory_required", "open_resources", "industry_order", "starter", "legacy_hidden",
    "unique", "tags",
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
    input_growth: float | None = None,
    output_growth: float | None = None,
    description: str = "",
    icon: str = "🏢",
    company_level_required: int = 1,
    prerequisites: Mapping[str, int] | None = None,
    territory_required: int = 0,
    open_resources: Mapping[str, float] | None = None,
    industry_order: int = 0,
    starter: bool = False,
    legacy_hidden: bool = False,
    unique: bool = True,
    tags: Sequence[str] = (),
) -> dict[str, Any]:
    """Return one normalized immutable catalog entry.

    ``income_growth`` is retained for backward compatibility with the first V2
    rollout. New resource enterprises use independent input/output growth so
    upgrades can improve efficiency instead of multiplying consumption and
    production by the same factor forever.
    """
    return {
        "id": business_id,
        "name": name,
        "description": description,
        "icon": icon,
        "tier": int(tier),
        "mechanic": mechanic,
        "specialization": specialization,
        "max_stage": int(max_stage),
        "slot_weight": int(slot_weight),
        "open_cost": float(open_cost),
        "base_income_per_hour": float(base_income_per_hour),
        "base_maintenance_per_hour": float(base_maintenance_per_hour),
        "income_growth": float(income_growth),
        "input_growth": float(input_growth if input_growth is not None else income_growth),
        "output_growth": float(output_growth if output_growth is not None else income_growth),
        "upgrade_cost_growth": float(upgrade_cost_growth),
        "upgrade_time_curve": upgrade_time_curve,
        "inputs_per_hour": dict(inputs_per_hour or {}),
        "outputs_per_hour": dict(outputs_per_hour or {}),
        "milestones": {int(stage): dict(value) for stage, value in (milestones or {}).items()},
        "upgrade_downtime_mult": float(upgrade_downtime_mult),
        "company_level_required": max(1, int(company_level_required)),
        "prerequisites": {str(key): int(value) for key, value in (prerequisites or {}).items()},
        "territory_required": max(0, int(territory_required)),
        "open_resources": {str(key): float(value) for key, value in (open_resources or {}).items()},
        "industry_order": int(industry_order),
        "starter": bool(starter),
        "legacy_hidden": bool(legacy_hidden),
        "unique": bool(unique),
        "tags": tuple(str(tag) for tag in tags),
    }
