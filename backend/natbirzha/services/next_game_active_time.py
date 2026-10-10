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
MAX_ACTIVE_MULTIPLIER = 1.5


def active_production_enabled() -> bool:
    value = os.getenv("NEXT_GAME_ACTIVE_PRODUCTION_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def active_cycle_multiplier(
    cycle_start: datetime,
    cycle_end: datetime,
    intervals: Iterable[tuple[datetime, datetime]],
) -> tuple[float, float]:
    """Integrate the union of server-confirmed intervals over one cycle."""
    duration = (cycle_end - cycle_start).total_seconds()
    if duration <= 0:
        return 1.0, 0
    clipped = sorted(
        (max(cycle_start, start), min(cycle_end, end))
        for start, end in intervals
        if end > cycle_start and start < cycle_end and end > start
    )
    merged: list[list[datetime]] = []
    for start, end in clipped:
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    seconds = min(duration, sum((end - start).total_seconds() for start, end in merged))
    seconds = round(max(0.0, seconds), 4)
    multiplier = min(MAX_ACTIVE_MULTIPLIER, 1.0 + 0.5 * seconds / duration)
    return round(multiplier, 8), seconds


async def active_multiplier_for_cycle(
    session: AsyncSession,
    company_id: int,
    cycle_start: datetime,
    cycle_end: datetime,
) -> tuple[float, float]:
    if not active_production_enabled():
        return 1.0, 0
    rows = (await session.execute(
        select(NatNextGameActiveInterval.start_at, NatNextGameActiveInterval.end_at).where(
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
