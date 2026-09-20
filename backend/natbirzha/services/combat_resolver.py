"""Pure, deterministic combined-arms battle calculation.

The resolver deliberately performs no database or clock access. Persisted battle
snapshots can therefore be replayed and audited with the same seed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
from typing import Mapping

from backend.natbirzha.services.unit_catalog import GROUND_UNITS, UNIT_CATALOG, validate_units


@dataclass(frozen=True)
class ArmySnapshot:
    units: Mapping[str, int]
    levels: Mapping[str, int] = field(default_factory=dict)
    readiness: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_units(self.units)


@dataclass(frozen=True)
class PremiumModifiers:
    recon: float = 0.0
    air: float = 0.0
    ground: float = 0.0
    defense: float = 0.0
    electronic_warfare: float = 0.0
    active_protection: float = 0.0


@dataclass(frozen=True)
class BattleResult:
    winner: str
    attacker_score: float
    defender_score: float
    attacker_random_multiplier: float
    defender_random_multiplier: float
    attacker_loss_fraction: float
    defender_loss_fraction: float
    attacker_losses: Mapping[str, int]
    defender_losses: Mapping[str, int]
    attacker_can_occupy: bool
    defender_can_occupy: bool
    phases: Mapping[str, Mapping[str, float]]


def _bounded_bonus(value: float) -> float:
    return 1.0 + min(0.20, max(0.0, float(value)))


def _random_multiplier(seed: str, side: str) -> float:
    digest = hashlib.sha256(f"{seed}:{side}".encode("utf-8")).digest()
    point = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
    return round(0.95 + point * 0.10, 8)


def _level_multiplier(army: ArmySnapshot, unit_name: str) -> float:
    level = max(0, int(army.levels.get(unit_name, 0)))
    return 1.0 + min(level, 20) * 0.03


def _readiness_multiplier(army: ArmySnapshot, unit_name: str) -> float:
    return min(1.0, max(0.25, float(army.readiness.get(unit_name, 1.0))))


def _unit_power(unit_name: str, quantity: int, own: ArmySnapshot, enemy: ArmySnapshot) -> float:
    spec = UNIT_CATALOG[unit_name]
    if not quantity:
        return 0.0
    counter = 1.0
    for target, multiplier in spec.counters.items():
        if enemy.units.get(target, 0) > 0:
            counter = max(counter, multiplier)
    return (
        quantity
        * spec.base_power
        * counter
        * _level_multiplier(own, unit_name)
        * _readiness_multiplier(own, unit_name)
    )


def _phase_power(army: ArmySnapshot, enemy: ArmySnapshot, phase: str) -> float:
    return sum(
        _unit_power(name, army.units.get(name, 0), army, enemy)
        for name, spec in UNIT_CATALOG.items()
        if spec.phase == phase
    )


def _recon_multiplier(own_recon: float, enemy_recon: float) -> float:
    total = own_recon + enemy_recon
    if total <= 0:
        return 1.0
    advantage = (own_recon - enemy_recon) / total
    return 1.0 + 0.12 * max(-1.0, min(1.0, advantage))


def _loss_fractions(attacker_score: float, defender_score: float) -> tuple[float, float]:
    """Return proportional casualties for a resolved engagement.

    A huge advantage still costs the expedition a small, visible force.  At
    near-parity, however, a victory is expensive; this prevents a player from
    farming PvE targets with one endlessly reusable army.
    """
    high = max(attacker_score, defender_score, 1.0)
    low = max(min(attacker_score, defender_score), 1.0)
    strength_ratio = high / low

    # At 10:1 the victor loses about 5%; at 3:2 it loses about 43%.
    winner_loss = min(0.60, max(0.05, 0.05 + 0.72 * math.exp(-1.2 * (strength_ratio - 1.0))))
    # The defeated side suffers at least the victor's losses and increasingly
    # severe losses as the matchup becomes one-sided.
    loser_loss = min(
        0.90,
        max(winner_loss, winner_loss + 0.20 + 0.45 * (1.0 - math.exp(-0.5 * (strength_ratio - 1.0)))),
    )
    if attacker_score > defender_score:
        return round(winner_loss, 6), round(loser_loss, 6)
    return round(loser_loss, 6), round(winner_loss, 6)


def _losses(
    units: Mapping[str, int],
    fraction: float,
    seed: str,
    side: str,
    active_protection: float = 0.0,
) -> dict[str, int]:
    result: dict[str, int] = {}
    for name, quantity in units.items():
        protected_fraction = fraction
        if name == "tanks":
            protected_fraction *= 1.0 - min(0.20, max(0.0, active_protection))
        exact = quantity * protected_fraction
        whole = math.floor(exact)
        remainder = exact - whole
        digest = hashlib.sha256(f"{seed}:{side}:loss:{name}".encode("utf-8")).digest()
        point = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
        result[name] = min(quantity, whole + int(point < remainder))
    return result


def _can_occupy(units: Mapping[str, int], losses: Mapping[str, int]) -> bool:
    return any(units.get(name, 0) - losses.get(name, 0) > 0 for name in GROUND_UNITS)


def resolve_battle(
    attacker: ArmySnapshot,
    defender: ArmySnapshot,
    *,
    seed: str,
    attacker_modifiers: PremiumModifiers | None = None,
    defender_modifiers: PremiumModifiers | None = None,
) -> BattleResult:
    """Resolve a battle from immutable inputs and a stable random seed."""

    if not seed:
        raise ValueError("Battle seed must not be empty")
    attacker_modifiers = attacker_modifiers or PremiumModifiers()
    defender_modifiers = defender_modifiers or PremiumModifiers()

    attacker_recon_premium = _bounded_bonus(attacker_modifiers.recon)
    defender_recon_premium = _bounded_bonus(defender_modifiers.recon)
    attacker_ew = min(0.20, max(0.0, attacker_modifiers.electronic_warfare))
    defender_ew = min(0.20, max(0.0, defender_modifiers.electronic_warfare))
    attacker_recon = _phase_power(attacker, defender, "recon") * attacker_recon_premium * (1.0 - defender_ew)
    defender_recon = _phase_power(defender, attacker, "recon") * defender_recon_premium * (1.0 - attacker_ew)
    attacker_recon_bonus = _recon_multiplier(attacker_recon, defender_recon)
    defender_recon_bonus = _recon_multiplier(defender_recon, attacker_recon)

    attacker_air_premium = _bounded_bonus(attacker_modifiers.air)
    defender_air_premium = _bounded_bonus(defender_modifiers.air + defender_modifiers.defense)
    attacker_ground_premium = _bounded_bonus(attacker_modifiers.ground)
    defender_ground_premium = _bounded_bonus(defender_modifiers.ground + defender_modifiers.defense)

    attacker_air = (
        _phase_power(attacker, defender, "air")
        + _phase_power(attacker, defender, "air_defense")
    ) * attacker_air_premium
    defender_air = (
        _phase_power(defender, attacker, "air")
        + _phase_power(defender, attacker, "air_defense")
    ) * defender_air_premium

    defender_guard_bonus = 1.30 if defender.units.get("border_guards", 0) else 1.0
    attacker_guard_bonus = 1.30 if attacker.units.get("border_guards", 0) else 1.0
    attacker_ground = _phase_power(attacker, defender, "ground") * attacker_ground_premium
    defender_ground = _phase_power(defender, attacker, "ground") * defender_ground_premium
    # Border guards apply their defensive doctrine only while defending.
    defender_ground *= defender_guard_bonus

    attacker_random = _random_multiplier(seed, "attacker")
    defender_random = _random_multiplier(seed, "defender")
    attacker_score = (attacker_air + attacker_ground + attacker_recon * 0.25) * attacker_recon_bonus * attacker_random
    defender_score = (defender_air + defender_ground + defender_recon * 0.25) * defender_recon_bonus * defender_random

    winner = "attacker" if attacker_score > defender_score else "defender"
    attacker_loss_fraction, defender_loss_fraction = _loss_fractions(attacker_score, defender_score)
    attacker_losses = _losses(
        attacker.units, attacker_loss_fraction, seed, "attacker", attacker_modifiers.active_protection
    )
    defender_losses = _losses(
        defender.units, defender_loss_fraction, seed, "defender", defender_modifiers.active_protection
    )

    phases = {
        "recon": {
            "attacker_power": attacker_recon,
            "defender_power": defender_recon,
            "attacker_accuracy": attacker_recon_bonus,
            "defender_accuracy": defender_recon_bonus,
            "attacker_premium": attacker_recon_premium,
            "defender_premium": defender_recon_premium,
            "attacker_ew": attacker_ew,
            "defender_ew": defender_ew,
        },
        "air": {
            "attacker_power": attacker_air,
            "defender_power": defender_air,
            "attacker_premium": attacker_air_premium,
            "defender_premium": defender_air_premium,
        },
        "ground": {
            "attacker_power": attacker_ground,
            "defender_power": defender_ground,
            "attacker_premium": attacker_ground_premium,
            "defender_premium": defender_ground_premium,
            "attacker_defense_bonus": attacker_guard_bonus,
            "defender_defense_bonus": defender_guard_bonus,
        },
    }
    return BattleResult(
        winner=winner,
        attacker_score=round(attacker_score, 6),
        defender_score=round(defender_score, 6),
        attacker_random_multiplier=attacker_random,
        defender_random_multiplier=defender_random,
        attacker_loss_fraction=attacker_loss_fraction,
        defender_loss_fraction=defender_loss_fraction,
        attacker_losses=attacker_losses,
        defender_losses=defender_losses,
        attacker_can_occupy=_can_occupy(attacker.units, attacker_losses),
        defender_can_occupy=_can_occupy(defender.units, defender_losses),
        phases=phases,
    )
