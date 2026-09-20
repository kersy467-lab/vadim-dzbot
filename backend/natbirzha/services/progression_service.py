"""Authoritative company XP and level progression."""

from __future__ import annotations

from typing import Any, Dict

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany


def _transition_cost(current_level: int) -> int:
    """XP earned while at ``current_level`` to unlock the next level.

    The quadratic term keeps the first few levels approachable while making
    the later eras materially longer. XP is cumulative and is never consumed.
    """

    if current_level < 1:
        raise ValueError("current_level must be positive")
    index = current_level - 1
    return int(150 + (35 * index) + (8 * index * index))


def xp_required_for_level(level: int) -> int:
    """Return cumulative XP required to have reached ``level``."""

    maximum = int(nat_settings.COMPANY_MAX_LEVEL)
    if level < 1 or level > maximum:
        raise ValueError(f"level must be between 1 and {maximum}")
    return sum(_transition_cost(current) for current in range(1, level))


def mastery_xp_required_for_rank(rank: int) -> int:
    """Return the cumulative, unbounded XP threshold for a mastery rank."""

    if rank < 0:
        raise ValueError("mastery rank cannot be negative")
    return int(nat_settings.MASTERY_XP_BASE) * rank * (rank + 1) // 2


def _mastery_snapshot(company: NatCompany) -> Dict[str, Any]:
    xp = max(0, int(getattr(company, "mastery_xp", 0) or 0))
    rank = max(0, int(getattr(company, "mastery_rank", 0) or 0))
    while xp >= mastery_xp_required_for_rank(rank + 1):
        rank += 1
    company.mastery_rank = rank
    current = mastery_xp_required_for_rank(rank)
    next_rank = mastery_xp_required_for_rank(rank + 1)
    span = max(1, next_rank - current)
    return {
        "rank": rank,
        "xp": xp,
        "current_rank_xp": current,
        "next_rank_xp": next_rank,
        "xp_to_next": max(0, next_rank - xp),
        "progress_pct": round(min(100.0, (xp - current) * 100 / span), 2),
        "is_unbounded": True,
    }


def progress_snapshot(company: NatCompany) -> Dict[str, Any]:
    """Serialize the canonical level progress used by API and UI."""

    maximum = int(nat_settings.COMPANY_MAX_LEVEL)
    era_size = max(1, int(nat_settings.COMPANY_ERA_SIZE))
    level = max(1, min(maximum, int(company.level or 1)))
    xp = max(0, int(company.xp or 0))
    era = min((maximum + era_size - 1) // era_size, ((level - 1) // era_size) + 1)
    current_threshold = xp_required_for_level(level)

    if level >= maximum:
        snapshot = {
            "level": level,
            "xp": xp,
            "current_level_xp": current_threshold,
            "next_level_xp": None,
            "xp_to_next": 0,
            "level_progress_pct": 100.0,
            "is_max_level": True,
            "max_level": maximum,
            "era": era,
        }
        snapshot["mastery"] = _mastery_snapshot(company)
        return snapshot

    next_threshold = xp_required_for_level(level + 1)
    span = max(1, next_threshold - current_threshold)
    earned_in_level = max(0, xp - current_threshold)
    progress_pct = round(min(100.0, (earned_in_level / span) * 100.0), 2)
    return {
        "level": level,
        "xp": xp,
        "current_level_xp": current_threshold,
        "next_level_xp": next_threshold,
        "xp_to_next": max(0, next_threshold - xp),
        "level_progress_pct": progress_pct,
        "is_max_level": False,
        "max_level": maximum,
        "era": era,
        "mastery": _mastery_snapshot(company),
    }


def apply_xp(company: NatCompany, amount: int) -> Dict[str, Any]:
    """Add XP, advance every crossed level, and never reduce legacy levels."""

    gain = int(amount)
    if gain < 0:
        raise ValueError("XP gain cannot be negative")

    maximum = int(nat_settings.COMPANY_MAX_LEVEL)
    previous_level = max(1, min(maximum, int(company.level or 1)))
    previous_xp = max(0, int(company.xp or 0))
    company.xp = previous_xp + gain

    derived_level = previous_level
    while derived_level < maximum and company.xp >= xp_required_for_level(derived_level + 1):
        derived_level += 1

    company.level = max(previous_level, derived_level)
    mastery_threshold = xp_required_for_level(maximum)
    mastery_gain = max(0, company.xp - mastery_threshold) - max(0, previous_xp - mastery_threshold)
    if mastery_gain:
        company.mastery_xp = max(0, int(getattr(company, "mastery_xp", 0) or 0)) + mastery_gain
    snapshot = progress_snapshot(company)
    snapshot["xp_gained"] = gain
    snapshot["levels_gained"] = company.level - previous_level
    return snapshot


__all__ = ["apply_xp", "mastery_xp_required_for_rank", "progress_snapshot", "xp_required_for_level"]
