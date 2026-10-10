"""Time-weighting and capacity-safe output for active production bonuses."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game_active import NatNextGameActiveInterval

HEARTBEAT_SECONDS = 15
MAX_HEARTBEAT_GAP_SECONDS = 30
ACTIVE_TIMEOUT_SECONDS = 90
IDLE_WARNING_SECONDS = 60
MAX_ACTIVE_MULTIPLIER = 5.0


def active_production_enabled() -> bool:
    value = os.getenv("NEXT_GAME_ACTIVE_PRODUCTION_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def active_cycle_multiplier(
    cycle_start: datetime,
    cycle_end: datetime,
    intervals: Iterable[tuple[datetime, datetime] | tuple[datetime, datetime, float]],
) -> tuple[float, float]:
    """Integrate server-confirmed multiplier intervals over one production cycle."""
    duration = (cycle_end - cycle_start).total_seconds()
    if duration <= 0:
        return 1.0, 0
    clipped: list[tuple[datetime, datetime, float]] = []
    for entry in intervals:
        start, end = entry[0], entry[1]
        # Two-column rows are pre-minigame activity records and retain their old 1.5x rate.
        factor = 1.5 if len(entry) == 2 else float(entry[2])
        if end <= cycle_start or start >= cycle_end or end <= start:
            continue
        clipped.append((max(cycle_start, start), min(cycle_end, end),
                        max(1.0, min(float(MAX_ACTIVE_MULTIPLIER), factor))))
    if not clipped:
        return 1.0, 0

    boundaries = sorted({point for start, end, _ in clipped for point in (start, end)})
    active_seconds = 0.0
    weighted_bonus_seconds = 0.0
    for left, right in zip(boundaries, boundaries[1:]):
        seconds = (right - left).total_seconds()
        if seconds <= 0:
            continue
        covering = [value for start, end, value in clipped if start < right and end > left]
        if covering:
            active_seconds += seconds
            weighted_bonus_seconds += seconds * (max(covering) - 1.0)
    active_seconds = round(min(duration, max(0.0, active_seconds)), 4)
    multiplier = 1.0 + weighted_bonus_seconds / duration
    return round(min(MAX_ACTIVE_MULTIPLIER, multiplier), 8), active_seconds


async def active_multiplier_for_cycle(
    session: AsyncSession,
    company_id: int,
    cycle_start: datetime,
    cycle_end: datetime,
) -> tuple[float, float]:
    if not active_production_enabled():
        return 1.0, 0
    rows = (await session.execute(
        select(
            NatNextGameActiveInterval.start_at,
            NatNextGameActiveInterval.end_at,
            NatNextGameActiveInterval.output_multiplier,
        ).where(
            NatNextGameActiveInterval.company_id == company_id,
            NatNextGameActiveInterval.start_at < cycle_end,
            NatNextGameActiveInterval.end_at > cycle_start,
        )
    )).all()
    return active_cycle_multiplier(cycle_start, cycle_end, rows)


def output_with_active_bonus(
    base_output: float,
    multiplier: float,
    capacity: float,
    stored: float,
    reserved: float = 0,
) -> tuple[float, float]:
    """Keep ordinary output and fit only the extra amount into free space."""
    base = max(0.0, float(base_output))
    requested = base * max(0.0, min(float(multiplier), MAX_ACTIVE_MULTIPLIER) - 1.0)
    room = max(0.0, float(capacity) - float(stored) - float(reserved) - base)
    room = int((room + 1e-9) * 10_000) / 10_000
    extra = round(min(requested, room), 4)
    final = round(base + extra, 4)
    return final, round(final - base, 4)


__all__ = [
    "ACTIVE_TIMEOUT_SECONDS", "HEARTBEAT_SECONDS", "IDLE_WARNING_SECONDS",
    "MAX_ACTIVE_MULTIPLIER", "MAX_HEARTBEAT_GAP_SECONDS",
    "active_cycle_multiplier", "active_multiplier_for_cycle", "active_production_enabled",
    "output_with_active_bonus",
]
