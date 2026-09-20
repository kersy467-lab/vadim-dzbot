"""Server-owned rate calculations for a settled idle business."""

from dataclasses import dataclass
from typing import Any

from backend.natbirzha.models.business import NatBusiness


@dataclass(frozen=True)
class CashBusinessRates:
    gross_per_hour: float
    maintenance_per_hour: float
    net_per_hour: float


def cash_business_rates(business: NatBusiness, spec: dict[str, Any], *, upgrading: bool) -> CashBusinessRates:
    """Calculate one business rate from persisted state and a server catalog spec."""
    stage = max(1, int(business.stage))
    income_multiplier = float(spec["income_growth"]) ** (stage - 1)
    for milestone_stage, milestone in spec.get("milestones", {}).items():
        if stage >= int(milestone_stage):
            income_multiplier *= float(milestone.get("income_multiplier", 1.0))

    effective_efficiency = max(0.0, float(business.efficiency or 0.0))
    effective_health = min(1.0, max(0.0, float(business.health or 0.0) / 100.0))
    downtime = float(spec["upgrade_downtime_mult"]) if upgrading else 1.0
    gross = float(business.base_income_per_hour) * income_multiplier * effective_efficiency * effective_health * downtime
    maintenance = float(business.base_maintenance_per_hour) * effective_efficiency
    return CashBusinessRates(
        gross_per_hour=round(gross, 4),
        maintenance_per_hour=round(maintenance, 4),
        net_per_hour=round(gross - maintenance, 4),
    )


__all__ = ["CashBusinessRates", "cash_business_rates"]
