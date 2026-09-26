"""Server-owned rate calculations for a settled idle business."""

from dataclasses import dataclass
from typing import Any

from backend.natbirzha.models.business import NatBusiness


@dataclass(frozen=True)
class CashBusinessRates:
    gross_per_hour: float
    maintenance_per_hour: float
    net_per_hour: float


@dataclass(frozen=True)
class ResourceBusinessRates:
    input_multiplier: float
    output_multiplier: float
    maintenance_per_hour: float


def _condition_multiplier(business: NatBusiness, spec: dict[str, Any], *, upgrading: bool) -> float:
    efficiency = max(0.0, float(business.efficiency or 0.0))
    health = min(1.0, max(0.0, float(business.health or 0.0) / 100.0))
    downtime = float(spec["upgrade_downtime_mult"]) if upgrading else 1.0
    return efficiency * health * downtime


def cash_business_rates(
    business: NatBusiness,
    spec: dict[str, Any],
    *,
    upgrading: bool,
    output_bonus_multiplier: float = 1.0,
) -> CashBusinessRates:
    stage = max(1, int(business.stage))
    income_multiplier = float(spec["income_growth"]) ** (stage - 1)
    for milestone_stage, milestone in spec.get("milestones", {}).items():
        if stage >= int(milestone_stage):
            income_multiplier *= float(milestone.get("income_multiplier", 1.0))
    condition = _condition_multiplier(business, spec, upgrading=upgrading)
    metadata = dict(business.metadata_json or {})
    asset_multiplier = max(0.0, float(metadata.get("asset_output_multiplier", 1.0) or 1.0))
    bonus = max(0.0, float(output_bonus_multiplier))
    gross = float(business.base_income_per_hour) * income_multiplier * condition * asset_multiplier * bonus
    maintenance = (
        float(business.base_maintenance_per_hour) * max(0.0, float(business.efficiency or 0.0))
        + max(0.0, float(metadata.get("asset_salary_per_hour", 0.0) or 0.0))
        + max(0.0, float(metadata.get("asset_maintenance_per_hour", 0.0) or 0.0))
    )
    return CashBusinessRates(
        gross_per_hour=round(gross, 4),
        maintenance_per_hour=round(maintenance, 4),
        net_per_hour=round(gross - maintenance, 4),
    )


def resource_business_rates(
    business: NatBusiness,
    spec: dict[str, Any],
    *,
    upgrading: bool,
    output_bonus_multiplier: float = 1.0,
) -> ResourceBusinessRates:
    """Return throughput, bounded material efficiency and paid upkeep."""
    stage = max(1, int(business.stage))
    input_multiplier = float(spec.get("input_growth", spec["income_growth"])) ** (stage - 1)
    output_multiplier = float(spec.get("output_growth", spec["income_growth"])) ** (stage - 1)
    for milestone_stage, milestone in spec.get("milestones", {}).items():
        if stage < int(milestone_stage):
            continue
        input_multiplier *= float(milestone.get("input_multiplier", 1.0))
        output_multiplier *= float(milestone.get("output_multiplier", 1.0))
    profile = spec.get("stage_rates", {}).get(min(stage, int(spec["max_stage"])))
    if profile:
        input_multiplier = float(profile["input"])
        output_multiplier = float(profile["output"])
    condition = _condition_multiplier(business, spec, upgrading=upgrading)
    metadata = dict(business.metadata_json or {})
    asset_multiplier = max(0.0, float(metadata.get("asset_output_multiplier", 1.0) or 1.0))
    input_multiplier *= condition
    output_multiplier *= condition * asset_multiplier * max(0.0, float(output_bonus_multiplier))
    maintenance = (
        float(business.base_maintenance_per_hour) * max(0.0, float(business.efficiency or 0.0))
        * (float(profile["maintenance"]) if profile else 1.0)
        + max(0.0, float(metadata.get("asset_salary_per_hour", 0.0) or 0.0))
        + max(0.0, float(metadata.get("asset_maintenance_per_hour", 0.0) or 0.0))
    )
    return ResourceBusinessRates(
        input_multiplier=round(input_multiplier, 6),
        output_multiplier=round(output_multiplier, 6),
        maintenance_per_hour=round(maintenance, 6),
    )


def resource_business_multiplier(business: NatBusiness, spec: dict[str, Any], *, upgrading: bool) -> float:
    """Backward-compatible alias for old tests and read models."""
    return resource_business_rates(business, spec, upgrading=upgrading).output_multiplier


__all__ = [
    "CashBusinessRates",
    "ResourceBusinessRates",
    "cash_business_rates",
    "resource_business_multiplier",
    "resource_business_rates",
]
