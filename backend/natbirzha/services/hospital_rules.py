"""Deterministic casualty classification and treatment balance rules."""

from __future__ import annotations

from collections.abc import Mapping
from math import floor

from backend.natbirzha.services.unit_catalog import UNIT_CATALOG


HUMAN_UNITS = frozenset({"infantry", "border_guards"})
REPAIR_UNITS = frozenset(set(UNIT_CATALOG) - HUMAN_UNITS)
HOSPITAL_BEDS_PER_LEVEL = 500
REPAIR_BAYS_PER_LEVEL = 50
MAX_HOSPITAL_LEVEL = 20
MAX_REPAIR_DEPOT_LEVEL = 20
MAX_HOSPITAL_CAPACITY = 10_000
MAX_REPAIR_DEPOT_CAPACITY = 1_000


def hospital_capacity(level: int) -> int:
    """Non-linear hospital capacity: starts smaller (120 at lvl 1) up to 10 000 beds at lvl 20."""
    lvl = max(0, min(MAX_HOSPITAL_LEVEL, int(level)))
    return 20 * lvl * (lvl + 5)


def repair_depot_capacity(level: int) -> int:
    """Non-linear repair depot capacity: starts smaller (12 at lvl 1) up to 1 000 bays at lvl 20."""
    lvl = max(0, min(MAX_REPAIR_DEPOT_LEVEL, int(level)))
    return 2 * lvl * (lvl + 5)

TREATMENT_CASH_PER_UNIT = {
    "infantry": 10.0,
    "border_guards": 20.0,
    "tanks": 200.0,
    "drones": 100.0,
    "air_defense": 300.0,
    "aircraft": 1_000.0,
}
REPAIR_MATERIALS_PER_UNIT = {
    "infantry": {},
    "border_guards": {},
    "tanks": {"steel": 0.5},
    "drones": {"electronics": 0.2},
    "air_defense": {"steel": 0.8, "electronics": 0.3},
    "aircraft": {"aluminum": 2.0, "jet_fuel": 1.0},
}
TREATMENT_BATCHES = {
    "infantry": (100, 1),
    "border_guards": (100, 1),
    "tanks": (10, 2),
    "drones": (20, 1),
    "air_defense": (5, 3),
    "aircraft": (2, 5),
}


def _round_half_up(value: float) -> int:
    return floor(value + 0.5)


def classify_losses(losses: Mapping[str, int], mode: str) -> dict[str, dict[str, int]]:
    """Split resolved combat losses using the approved PvE/PvP percentages."""
    normalized_mode = str(mode).strip().upper()
    if normalized_mode not in {"PVE", "PVP"}:
        raise ValueError("Battle mode must be PVE or PVP")

    light_wounded: dict[str, int] = {}
    severe_wounded: dict[str, int] = {}
    fatalities: dict[str, int] = {}
    for unit_type, raw_count in losses.items():
        if unit_type not in UNIT_CATALOG:
            raise ValueError(f"Unknown military unit: {unit_type}")
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 0:
            raise ValueError("Loss quantities must be non-negative integers")
        count = int(raw_count)
        if normalized_mode == "PVE":
            dead = 0
            severe = _round_half_up(count * 0.30)
        else:
            dead = _round_half_up(count * 0.07)
            severe = _round_half_up(count * 0.38)
        severe = min(severe, count - dead)
        light = count - severe - dead
        light_wounded[unit_type] = light
        severe_wounded[unit_type] = severe
        fatalities[unit_type] = dead

    return {
        "light_wounded": light_wounded,
        "severe_wounded": severe_wounded,
        "fatalities": fatalities,
    }


def allocate_capacity(losses: Mapping[str, int], capacity: int) -> dict[str, int]:
    """Admit severe casualties proportionally into a shared facility capacity."""
    normalized = {key: int(value) for key, value in losses.items() if int(value) > 0}
    total = sum(normalized.values())
    admitted = min(max(0, int(capacity)), total)
    if not total or not admitted:
        return {key: 0 for key in normalized}
    if admitted == total:
        return normalized.copy()

    exact = {key: quantity * admitted / total for key, quantity in normalized.items()}
    result = {key: floor(value) for key, value in exact.items()}
    remainder = admitted - sum(result.values())
    for key in sorted(normalized, key=lambda item: (-(exact[item] - result[item]), item))[:remainder]:
        result[key] += 1
    return result


def treatment_duration_minutes(unit_type: str, count: int) -> int:
    if unit_type not in TREATMENT_BATCHES:
        raise ValueError("Неизвестный тип войск")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("Количество должно быть положительным целым числом")
    batch_size, minutes_per_batch = TREATMENT_BATCHES[unit_type]
    return max(1, (count + batch_size - 1) // batch_size) * minutes_per_batch