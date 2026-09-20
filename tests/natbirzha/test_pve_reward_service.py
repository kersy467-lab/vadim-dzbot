"""Pure checks for PvE anti-farm cash compensation."""

from backend.natbirzha.services.pve_reward_service import PveRewardService


def run() -> None:
    light = PveRewardService.cash_reward(
        configured_cap=2_500,
        losses={"infantry": 10},
    )
    assert light["replacement_cash"] == 500.0
    assert light["cash"] == 325.0
    assert light["cash"] < light["replacement_cash"]

    capped = PveRewardService.cash_reward(
        configured_cap=2_500,
        losses={"infantry": 200},
    )
    assert capped["replacement_cash"] == 10_000.0
    assert capped["cash"] == 2_500.0

    zero = PveRewardService.cash_reward(configured_cap=55_000, losses={})
    assert zero["cash"] == 0.0
    assert zero["replacement_cash"] == 0.0

    mixed = PveRewardService.cash_reward(
        configured_cap=50_000,
        losses={"tanks": 10, "aircraft": 2, "drones": 5},
    )
    assert mixed["replacement_cash"] == 22_500.0
    assert mixed["cash"] == 14_625.0
    assert mixed["cash"] <= mixed["replacement_cash"]

    print("NATBIRZHA PvE reward checks: PASS")


if __name__ == "__main__":
    run()
