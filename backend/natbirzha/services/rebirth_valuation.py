"""Keep rebirth stock prices anchored without carrying old wealth multipliers."""

from __future__ import annotations

import math


MIN_COMPANY_VALUATION = 50_000.0


def rebase_valuation_anchor(
    rebirth_price: float,
    total_shares: int,
    raw_valuation: float,
) -> tuple[float, float]:
    """Return the rebirth market-cap anchor and audited baseline for future growth."""
    anchor = max(0.01, float(rebirth_price)) * max(1, int(total_shares or 1))
    baseline = max(MIN_COMPANY_VALUATION, float(raw_valuation or 0.0))
    return round(anchor, 2), round(baseline, 2)


def recover_rebirth_anchor(
    *, first_price: float, total_shares: int, legacy_scale: float
) -> tuple[float, float]:
    """Recover legacy rebirth data from its first quote and stored multiplier."""
    anchor, _ = rebase_valuation_anchor(first_price, total_shares, MIN_COMPANY_VALUATION)
    scale = float(legacy_scale or 0.0)
    baseline = anchor / scale if math.isfinite(scale) and scale > 1e-9 else MIN_COMPANY_VALUATION
    if not math.isfinite(baseline):
        baseline = MIN_COMPANY_VALUATION
    return anchor, round(max(MIN_COMPANY_VALUATION, baseline), 2)


def anchored_rebirth_valuation(
    *, raw_valuation: float, anchor: float, baseline: float
) -> float:
    """Add post-rebirth changes to the announced 1% market-cap starting point."""
    raw = max(MIN_COMPANY_VALUATION, float(raw_valuation or 0.0))
    return round(max(MIN_COMPANY_VALUATION, float(anchor) + raw - float(baseline)), 2)


__all__ = [
    "MIN_COMPANY_VALUATION",
    "anchored_rebirth_valuation",
    "rebase_valuation_anchor",
    "recover_rebirth_anchor",
]
