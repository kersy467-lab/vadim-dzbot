"""Deterministic combined-arms combat resolver checks."""

from backend.natbirzha.services.combat_resolver import (
    ArmySnapshot,
    PremiumModifiers,
    resolve_battle,
)


def army(**units: int) -> ArmySnapshot:
    return ArmySnapshot(units=units)


def run() -> None:
    tanks = resolve_battle(army(tanks=1), army(infantry=10), seed="tanks")
    assert tanks.winner == "attacker"

    aircraft = resolve_battle(army(aircraft=1), army(tanks=1), seed="aircraft")
    assert aircraft.winner == "attacker"

    air_defense = resolve_battle(army(air_defense=1), army(aircraft=1), seed="air-defense")
    assert air_defense.winner == "attacker"

    guards = resolve_battle(army(infantry=1), army(border_guards=1), seed="guards")
    assert guards.winner == "defender"
    assert guards.phases["ground"]["defender_defense_bonus"] == 1.30

    first = resolve_battle(army(infantry=100, drones=4), army(infantry=90, drones=2), seed="same")
    second = resolve_battle(army(infantry=100, drones=4), army(infantry=90, drones=2), seed="same")
    assert first == second
    assert 0.95 <= first.attacker_random_multiplier <= 1.05
    assert 0.95 <= first.defender_random_multiplier <= 1.05

    for result in (tanks, aircraft, air_defense, guards, first):
        winner_losses = result.attacker_loss_fraction if result.winner == "attacker" else result.defender_loss_fraction
        loser_losses = result.defender_loss_fraction if result.winner == "attacker" else result.attacker_loss_fraction
        assert 0.05 <= winner_losses <= 0.60
        assert winner_losses <= loser_losses
        assert all(value >= 0 for value in result.attacker_losses.values())
        assert all(value >= 0 for value in result.defender_losses.values())

    # A lopsided victory costs a small expeditionary force, rather than making
    # wars free.  A close victory is expensive enough that repeatedly farming
    # equal-strength PvE corporations is not optimal.
    overwhelming = resolve_battle(army(infantry=2000), army(infantry=200), seed="overwhelming")
    close = resolve_battle(army(infantry=300), army(infantry=200), seed="close")
    assert overwhelming.winner == "attacker"
    assert 80 <= overwhelming.attacker_losses["infantry"] <= 130
    assert close.winner == "attacker"
    assert 130 <= close.attacker_losses["infantry"] <= 190
    assert close.attacker_loss_fraction > overwhelming.attacker_loss_fraction

    capped = resolve_battle(
        army(infantry=100),
        army(infantry=100),
        seed="premium-cap",
        attacker_modifiers=PremiumModifiers(ground=5.0),
    )
    assert capped.phases["ground"]["attacker_premium"] == 1.20

    no_ground = resolve_battle(army(aircraft=10), army(infantry=1), seed="occupation")
    assert no_ground.winner == "attacker"
    assert no_ground.attacker_can_occupy is False

    print("NATBIRZHA combined-arms resolver checks: PASS")


if __name__ == "__main__":
    run()
