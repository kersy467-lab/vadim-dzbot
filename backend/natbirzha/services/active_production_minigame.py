"""Server-side timing rules for the active-production rhythm mini-game."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

WHEEL_SPEED_DEGREES_PER_SECOND = 110.0
GOLD_ZONE_HALF_WIDTH = 28.0
BLUE_ZONE_HALF_WIDTH = 22.0
TARGET_BAR_HALF_WIDTH = 12.0
TARGET_BAR_COUNT = 5
TARGET_BAR_RESPAWN_DELAY_MS = 850
MIN_TAP_INTERVAL_SECONDS = 0.12
SKILL_BOOST_SECONDS = 20
MAX_SKILL_CHARGE = 16
MAX_OUTPUT_MULTIPLIER = 5.0


def normalize_angle(angle: float) -> float:
    return round(float(angle) % 360.0, 6)


def angular_distance(left: float, right: float) -> float:
    return abs((float(left) - float(right) + 180.0) % 360.0 - 180.0)


def advance_wheel(angle: float, direction: int, speed: float, seconds: float) -> float:
    sign = 1 if int(direction) >= 0 else -1
    return normalize_angle(float(angle) + sign * float(speed) * max(0.0, float(seconds)))


def grade_tap(pointer_angle: float, target_angle: float) -> str:
    if angular_distance(pointer_angle, target_angle) <= GOLD_ZONE_HALF_WIDTH:
        return "gold"
    if angular_distance(pointer_angle, normalize_angle(target_angle + 180.0)) <= BLUE_ZONE_HALF_WIDTH:
        return "blue"
    return "miss"


def server_epoch_millis(value: datetime) -> int:
    """Convert the game's naive-UTC or aware timestamp to an unambiguous epoch value."""
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return int(utc_value.timestamp() * 1000)


def create_target_bars() -> list[dict]:
    """Create a Dota-style dial with several independent, clickable target bars."""
    first_angle = secrets.randbelow(36_000) / 100
    jitter = [secrets.randbelow(1_201) / 100 - 6 for _ in range(TARGET_BAR_COUNT)]
    return [{
        "id": secrets.token_hex(5),
        "angle": normalize_angle(first_angle + index * (360 / TARGET_BAR_COUNT) + jitter[index]),
        "kind": "blue" if index == 2 else "gold",
        "visible_at_ms": 0,
    } for index in range(TARGET_BAR_COUNT)]


def hit_target_bar(pointer_angle: float, bars: list[dict], at_ms: int) -> dict | None:
    """Return the nearest currently visible target under the pick, if any."""
    hits = [bar for bar in bars
            if int(bar.get("visible_at_ms", 0)) <= int(at_ms)
            and bar.get("kind") in {"gold", "blue"}
            and angular_distance(pointer_angle, float(bar.get("angle", 0))) <= TARGET_BAR_HALF_WIDTH]
    return min(hits, key=lambda bar: angular_distance(pointer_angle, float(bar["angle"])), default=None)


def replace_target_bar(bars: list[dict], consumed_id: str, at_ms: int) -> list[dict]:
    """Consume a hit bar and schedule its replacement after a short visible gap."""
    remaining = [dict(bar) for bar in bars if str(bar.get("id")) != str(consumed_id)]
    if len(remaining) == len(bars):
        return [dict(bar) for bar in bars]

    minimum_spacing = TARGET_BAR_HALF_WIDTH * 2 + 6
    angle = 0.0
    for _ in range(100):
        candidate = secrets.randbelow(36_000) / 100
        if all(angular_distance(candidate, float(bar.get("angle", 0))) >= minimum_spacing
               for bar in remaining):
            angle = candidate
            break
    else:
        angle = normalize_angle(float(remaining[-1].get("angle", 0)) + minimum_spacing)

    remaining.append({
        "id": secrets.token_hex(5),
        "angle": angle,
        "kind": "blue" if secrets.randbelow(5) == 0 else "gold",
        "visible_at_ms": int(at_ms) + TARGET_BAR_RESPAWN_DELAY_MS,
    })
    return remaining


def apply_tap_result(charge: int, streak: int, result: str) -> tuple[int, int]:
    current_charge = max(0, min(MAX_SKILL_CHARGE, int(charge)))
    current_streak = max(0, int(streak))
    if result == "gold":
        return min(MAX_SKILL_CHARGE, current_charge + 2), current_streak + 1
    if result == "blue":
        return min(MAX_SKILL_CHARGE, current_charge + 1), current_streak + 1
    if result == "miss":
        return max(0, current_charge - 1), 0
    raise ValueError("Неизвестный результат попадания")


def multiplier_for_charge(charge: int) -> float:
    safe_charge = max(0, min(MAX_SKILL_CHARGE, int(charge)))
    return min(MAX_OUTPUT_MULTIPLIER, 1.0 + safe_charge * 0.25)


def average_interval_multiplier(
    start: datetime,
    end: datetime,
    charge: int,
    last_tap_at: datetime | None,
) -> float:
    duration = max(0.0, (end - start).total_seconds())
    if duration <= 0 or last_tap_at is None or charge <= 0:
        return 1.0
    boosted_end = last_tap_at + timedelta(seconds=SKILL_BOOST_SECONDS)
    boosted_start = max(start, last_tap_at)
    boosted_end = min(end, boosted_end)
    boosted_seconds = max(0.0, (boosted_end - boosted_start).total_seconds())
    factor = multiplier_for_charge(charge)
    return round(1.0 + (factor - 1.0) * min(duration, boosted_seconds) / duration, 8)


def timing_state(row: object, now: datetime) -> dict:
    try:
        target_bars = json.loads(getattr(row, "target_bars_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        target_bars = []
    return {
        "pointer_angle": float(row.wheel_angle),
        "target_angle": float(row.target_angle),
        "target_bars": target_bars,
        "direction": int(row.wheel_direction),
        "speed": WHEEL_SPEED_DEGREES_PER_SECOND,
        "gold_half_width": GOLD_ZONE_HALF_WIDTH,
        "blue_half_width": BLUE_ZONE_HALF_WIDTH,
        "target_half_width": TARGET_BAR_HALF_WIDTH,
        "minimum_tap_seconds": MIN_TAP_INTERVAL_SECONDS,
        "charge": max(0, min(MAX_SKILL_CHARGE, int(row.skill_charge))),
        "streak": max(0, int(row.hit_streak)),
        "multiplier": multiplier_for_charge(row.skill_charge),
        "maximum_multiplier": MAX_OUTPUT_MULTIPLIER,
        "server_now": now.isoformat(),
        "server_now_ms": server_epoch_millis(now),
    }


__all__ = [
    "BLUE_ZONE_HALF_WIDTH", "GOLD_ZONE_HALF_WIDTH", "MAX_OUTPUT_MULTIPLIER",
    "MAX_SKILL_CHARGE", "MIN_TAP_INTERVAL_SECONDS", "SKILL_BOOST_SECONDS",
    "TARGET_BAR_COUNT", "TARGET_BAR_HALF_WIDTH", "TARGET_BAR_RESPAWN_DELAY_MS",
    "WHEEL_SPEED_DEGREES_PER_SECOND", "advance_wheel", "angular_distance",
    "apply_tap_result", "average_interval_multiplier", "create_target_bars",
    "grade_tap", "hit_target_bar", "multiplier_for_charge", "normalize_angle",
    "replace_target_bar", "server_epoch_millis", "timing_state",
]
