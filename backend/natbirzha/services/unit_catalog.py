"""Canonical military unit data used by the NATBIRZHA battle engine."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class UnitSpec:
    """Static combat properties for one unit type."""

    base_power: int
    phase: str
    defense: float = 1.0
    counters: Mapping[str, float] = field(default_factory=dict)


UNIT_CATALOG: Mapping[str, UnitSpec] = MappingProxyType(
    {
        "infantry": UnitSpec(base_power=10, phase="ground"),
        "border_guards": UnitSpec(base_power=14, phase="ground", defense=1.30),
        "tanks": UnitSpec(
            base_power=150,
            phase="ground",
            counters=MappingProxyType({"infantry": 1.25, "border_guards": 1.25}),
        ),
        "drones": UnitSpec(base_power=80, phase="recon"),
        "aircraft": UnitSpec(
            base_power=220,
            phase="air",
            counters=MappingProxyType({"tanks": 1.35}),
        ),
        "air_defense": UnitSpec(
            base_power=200,
            phase="air_defense",
            counters=MappingProxyType({"aircraft": 1.45}),
        ),
    }
)

GROUND_UNITS = frozenset({"infantry", "border_guards", "tanks"})


def validate_units(units: Mapping[str, int]) -> None:
    """Reject unknown units and invalid quantities at the resolver boundary."""

    unknown = set(units) - set(UNIT_CATALOG)
    if unknown:
        raise ValueError(f"Unknown military units: {', '.join(sorted(unknown))}")
    if any(isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0 for quantity in units.values()):
        raise ValueError("Unit quantities must be non-negative integers")

