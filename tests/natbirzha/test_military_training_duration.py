"""All military unit training times follow the shared reduction policy."""

from backend.natbirzha.services.military_infrastructure_service import (
    training_duration_minutes,
)


def test_training_is_twenty_percent_faster_for_every_unit_type() -> None:
    expected_minutes_for_100_units = {
        "infantry": 26,
        "border_guards": 44,
        "tanks": 154,
        "drones": 66,
        "aircraft": 397,
        "air_defense": 220,
    }

    for unit_type, expected_minutes in expected_minutes_for_100_units.items():
        assert training_duration_minutes(unit_type, count=100, speed=1.0) == expected_minutes


def test_training_time_never_falls_below_one_minute() -> None:
    assert training_duration_minutes("infantry", count=1, speed=100.0) == 1
