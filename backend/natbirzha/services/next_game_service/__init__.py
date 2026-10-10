"""Backward-compatible facade for the isolated NATBIRZHA 2.0 economy."""
from .common import *
from .core import NextGameCoreMixin
from .finance import NextGameFinanceMixin
from .production import NextGameProductionMixin
from .snapshot import NextGameSnapshotMixin

class NextGameService(
    NextGameSnapshotMixin,
    NextGameFinanceMixin,
    NextGameProductionMixin,
    NextGameCoreMixin,
):
    """Stable public API composed from focused service modules."""
    pass

__all__ = ["NextGameService"]
