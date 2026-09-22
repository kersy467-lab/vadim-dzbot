"""Checks for the non-blocking midgame IPO capital recommendation."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.capital_plan_service import capital_plan_for_company


def company(level: int, cash: float) -> NatCompany:
    return NatCompany(
        user_id=990_000 + level,
        name=f"Capital Plan {level}",
        specialization="agrarian",
        level=level,
        cash=cash,
    )


def run() -> None:
    early = capital_plan_for_company(company(17, 10_000), is_public=False)
    assert early["recommended"] is False
    assert early["state"] == "grow_first"

    short_on_cash = capital_plan_for_company(company(18, 10_000), is_public=False)
    assert short_on_cash["recommended"] is True
    assert short_on_cash["state"] == "ipo_recommended"
    assert short_on_cash["action"]["tab"] == "market"
    assert short_on_cash["min_dividend_pct"] == 5.0
    assert short_on_cash["project"]["cost"] > short_on_cash["cash"]

    self_funded = capital_plan_for_company(company(18, 2_000_000), is_public=False)
    assert self_funded["recommended"] is False
    assert self_funded["state"] == "self_funded"

    public = capital_plan_for_company(company(18, 10_000), is_public=True)
    assert public["recommended"] is False
    assert public["state"] == "public"

    print("NATBIRZHA CAPITAL PLAN CHECKS: PASS")


if __name__ == "__main__":
    run()
