"""PvE reward rules that keep repeat wars from becoming a cash faucet."""

from __future__ import annotations

from typing import Mapping

from backend.natbirzha.services.army_service import RECRUITMENT_CATALOG


PVE_CASH_RECOVERY_SHARE = 0.65


class PveRewardService:
    @staticmethod
    def replacement_cash_cost(losses: Mapping[str, int]) -> float:
        """Cash part of restoring the exact units lost in a battle.

        Material inputs are intentionally excluded. This makes the estimate a
        conservative lower bound for the player's real recovery cost.
        """
        total = 0.0
        for unit_type, count in losses.items():
            spec = RECRUITMENT_CATALOG.get(unit_type)
            if spec is None or count <= 0:
                continue
            total += float(spec["cash_cost"]) * int(count)
        return round(total, 2)

    @classmethod
    def cash_reward(cls, *, configured_cap: float, losses: Mapping[str, int]) -> dict[str, float]:
        replacement_cash = cls.replacement_cash_cost(losses)
        recovery_budget = round(replacement_cash * PVE_CASH_RECOVERY_SHARE, 2)
        awarded = round(min(max(float(configured_cap), 0.0), recovery_budget), 2)
        return {
            "cash": awarded,
            "configured_cap": round(max(float(configured_cap), 0.0), 2),
            "replacement_cash": replacement_cash,
            "recovery_share": PVE_CASH_RECOVERY_SHARE,
        }
