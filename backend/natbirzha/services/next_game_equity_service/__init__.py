"""Backward-compatible facade for the isolated 2.0 equity services."""

from .core import NextGameEquityCoreMixin
from .dividends import NextGameEquityDividendMixin
from .snapshot import NextGameEquitySnapshotMixin


class NextGameEquityService(
    NextGameEquitySnapshotMixin,
    NextGameEquityDividendMixin,
    NextGameEquityCoreMixin,
):
    """IPO lifecycle, protected share market and cash dividends."""


__all__ = ["NextGameEquityService"]
