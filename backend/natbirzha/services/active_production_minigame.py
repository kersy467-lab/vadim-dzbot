"""Server-side timing rules for the active-production rhythm mini-game."""

from __future__ import annotations

from datetime import datetime, timedelta

WHEEL_SPEED_DEGREES_PER_SECOND = 132.0
GOLD_ZONE_HALF_WIDTH = 28.0
BLUE_ZONE_HALF_WIDTH = 22.0
MIN_TAP_INTERVAL_SECONDS = 0.45
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
    return {
        "pointer_angle": float(row.wheel_angle),
        "target_angle": float(row.target_angle),
        "direction": int(row.wheel_direction),
        "speed": WHEEL_SPEED_DEGREES_PER_SECOND,
        "gold_half_width": GOLD_ZONE_HALF_WIDTH,
        "blue_half_width": BLUE_ZONE_HALF_WIDTH,
        "minimum_tap_seconds": MIN_TAP_INTERVAL_SECONDS,
        "charge": max(0, min(MAX_SKILL_CHARGE, int(row.skill_charge))),
        "streak": max(0, int(row.hit_streak)),
        "multiplier": multiplier_for_charge(row.skill_charge),
        "maximum_multiplier": MAX_OUTPUT_MULTIPLIER,
        "server_now": now.isoformat(),
    }


__all__ = [
    "BLUE_ZONE_HALF_WIDTH", "GOLD_ZONE_HALF_WIDTH", "MAX_OUTPUT_MULTIPLIER",
    "MAX_SKILL_CHARGE", "MIN_TAP_INTERVAL_SECONDS", "SKILL_BOOST_SECONDS",
    "WHEEL_SPEED_DEGREES_PER_SECOND", "advance_wheel", "angular_distance",
    "apply_tap_result", "average_interval_multiplier", "grade_tap",
    "multiplier_for_charge", "normalize_angle", "timing_state",
]
