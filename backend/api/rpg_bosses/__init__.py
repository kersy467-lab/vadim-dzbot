from typing import Dict, Any, Optional
from .roster_early import EARLY_BOSSES
from .roster_late import LATE_BOSSES

# Unified Raid Bosses Roster (100% Backward Compatible)
RAID_BOSSES: Dict[str, Any] = {**EARLY_BOSSES, **LATE_BOSSES}


def get_raid_boss_by_id(boss_id: str) -> Optional[Dict[str, Any]]:
    """Returns boss dictionary by boss identifier."""
    return RAID_BOSSES.get(boss_id)


def format_hp(hp: int) -> str:
    """Formats large health numbers into readable units."""
    if hp >= 1_000_000_000_000_000:
        return f"{hp / 1_000_000_000_000_000:.1f}Q"
    if hp >= 1_000_000_000_000:
        return f"{hp / 1_000_000_000_000:.1f}T"
    if hp >= 1_000_000_000:
        return f"{hp / 1_000_000_000:.1f}B"
    if hp >= 1_000_000:
        return f"{hp / 1_000_000:.1f}M"
    if hp >= 1_000:
        return f"{hp / 1_000:.0f}k"
    return str(hp)


__all__ = ["RAID_BOSSES", "get_raid_boss_by_id", "format_hp"]
