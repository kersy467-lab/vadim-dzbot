"""Process server-authoritative input for the active-production lock mini-game."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from backend.natbirzha.services.active_production_minigame import (
    MIN_TAP_INTERVAL_SECONDS, WHEEL_SPEED_DEGREES_PER_SECOND, advance_wheel,
    apply_tap_result, create_target_bars, hit_target_bar, replace_target_bar,
    server_epoch_millis,
)


def _resolve_tap_at(last_ping_at: datetime, current: datetime, tap_at_ms: int | None) -> datetime:
    if tap_at_ms is None:
        return current
    try:
        requested = datetime.fromtimestamp(int(tap_at_ms) / 1000, timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError, TypeError):
        return current
    # Accept measured client input time, but never let it select an arbitrary old wheel state.
    if requested < last_ping_at - timedelta(milliseconds=250):
        return current
    if requested > current + timedelta(milliseconds=150):
        return current
    return min(current, max(last_ping_at, requested))


def _load_target_bars(row: object) -> list[dict]:
    try:
        decoded = json.loads(getattr(row, "target_bars_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        decoded = []
    return [bar for bar in decoded if isinstance(bar, dict)] if isinstance(decoded, list) else []


def process_active_input(
    row: object,
    current: datetime,
    scene_action: str,
    user_input_counter: int,
    tap_at_ms: int | None = None,
) -> str | None:
    """Advance the pick to now and resolve a tap at its captured client time."""
    elapsed = max(0.0, (current - row.last_ping_at).total_seconds())
    original_direction = row.wheel_direction
    pointer_angle = advance_wheel(
        row.wheel_angle, original_direction, WHEEL_SPEED_DEGREES_PER_SECOND, elapsed,
    )
    target_bars = _load_target_bars(row) or create_target_bars()
    tap_result = None
    direction_after_tap = original_direction
    tap_at = current
    tap_angle = None
    applied_tap = False

    if scene_action == "tap" and user_input_counter > row.last_user_input_counter:
        tap_at = _resolve_tap_at(row.last_ping_at, current, tap_at_ms)
        since_tap = (
            (tap_at - row.last_skill_tap_at).total_seconds()
            if row.last_skill_tap_at else MIN_TAP_INTERVAL_SECONDS
        )
        if since_tap >= MIN_TAP_INTERVAL_SECONDS:
            tap_angle = advance_wheel(
                row.wheel_angle,
                original_direction,
                WHEEL_SPEED_DEGREES_PER_SECOND,
                max(0.0, (tap_at - row.last_ping_at).total_seconds()),
            )
            target = hit_target_bar(tap_angle, target_bars, server_epoch_millis(tap_at))
            tap_result = target["kind"] if target else "miss"
            row.skill_charge, row.hit_streak = apply_tap_result(
                row.skill_charge, row.hit_streak, tap_result,
            )
            row.last_skill_tap_at = tap_at
            row.last_interaction_at = current
            row.last_user_input_counter = user_input_counter
            if target:
                target_bars = replace_target_bar(
                    target_bars, str(target["id"]), server_epoch_millis(tap_at),
                )
                direction_after_tap = -original_direction
            applied_tap = True
        else:
            tap_result = "too_soon"

    if applied_tap and tap_angle is not None:
        pointer_angle = advance_wheel(
            tap_angle,
            direction_after_tap,
            WHEEL_SPEED_DEGREES_PER_SECOND,
            max(0.0, (current - tap_at).total_seconds()),
        )
        row.wheel_direction = direction_after_tap
    row.wheel_angle = pointer_angle
    row.target_bars_json = json.dumps(target_bars, separators=(",", ":"))
    return tap_result


__all__ = ["process_active_input"]
