"""Company progression must remain authoritative and scalable to level 60."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.progression_service import (
    apply_xp,
    mastery_xp_required_for_rank,
    progress_snapshot,
    xp_required_for_level,
)


def run() -> None:
    expected_thresholds = {
        1: 0,
        5: 922,
        10: 4242,
        30: 80272,
        60: 602567,
    }
    for level, expected in expected_thresholds.items():
        assert xp_required_for_level(level) == expected, (
            f"level {level} threshold changed: expected {expected}, got {xp_required_for_level(level)}"
        )

    company = NatCompany(
        user_id=980001,
        name="Long Progression",
        specialization="technoprom",
        level=1,
        xp=0,
    )
    gained = xp_required_for_level(10)
    result = apply_xp(company, gained)
    assert result["levels_gained"] == 9
    assert company.level == 10 and company.xp == gained

    apply_xp(company, xp_required_for_level(60) - company.xp + 999_999)
    assert company.level == 60, "company level must never exceed the configured level-60 cap"

    capped = progress_snapshot(company)
    assert capped["level"] == 60
    assert capped["is_max_level"] is True
    assert capped["next_level_xp"] is None
    assert capped["xp_to_next"] == 0
    assert capped["era"] == 6
    assert capped["mastery"]["rank"] > 0
    assert capped["mastery"]["xp"] > 0
    assert capped["mastery"]["next_rank_xp"] > capped["mastery"]["xp"]
    assert mastery_xp_required_for_rank(0) == 0
    assert mastery_xp_required_for_rank(1) > 0
    assert mastery_xp_required_for_rank(2) > mastery_xp_required_for_rank(1)

    legacy = NatCompany(
        user_id=980002,
        name="Legacy Progression",
        specialization="miner",
        level=5,
        xp=600,
    )
    apply_xp(legacy, 1)
    assert legacy.level == 5, "migration to the new curve must never reduce an existing company level"

    print("NATBIRZHA sixty-level progression checks: PASS")


if __name__ == "__main__":
    run()
