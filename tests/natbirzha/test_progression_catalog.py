"""Regression checks for reachable early production and premium catalog wiring."""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.natbirzha.services.building_catalog import CANONICAL_BUILDINGS
from backend.natbirzha.services.premium_catalog import PREMIUM_LICENSES
from backend.natbirzha.services.recipes import validate_recipe_dag


PREMIUM_RARE_ITEMS = {"lithium_raw", "cobalt_raw", "rare_earths", "gallium_raw"}


def run() -> None:
    chip = CANONICAL_BUILDINGS["chip_factory"]
    assert chip["level_required"] <= 10
    assert not (set(chip["inputs"]) & PREMIUM_RARE_ITEMS), (
        "The normal level-2 technoprom chain must not hard-require premium rare resources"
    )

    rare_license = PREMIUM_LICENSES["rare_mining"]
    assert set(rare_license.permitted_buildings) == {"lithium_mine", "rare_earth_mine"}
    assert set(rare_license.permitted_recipes) == {"mine_lithium", "mine_rare_earths"}

    by_industry = defaultdict(list)
    for building_id, spec in CANONICAL_BUILDINGS.items():
        level = int(spec["level_required"])
        assert 1 <= level <= 60, f"{building_id} unlock must fit the 1-60 company track"
        if level < 41:
            premium_inputs = set(spec.get("inputs", {})) & PREMIUM_RARE_ITEMS
            assert not premium_inputs, (
                f"{building_id} requires premium rare inputs too early at level {level}: {premium_inputs}"
            )
        by_industry[spec["specialization"]].append(level)

    assert len(by_industry) == 8, "the established eight industries must remain playable"
    for industry, levels in by_industry.items():
        assert len(levels) >= 10, f"{industry} needs at least ten distinct factory choices"
        assert min(levels) == 1, f"{industry} needs a level-1 starter"
        assert max(levels) >= 51, f"{industry} needs real endgame production in the 51-60 era"
        eras = {((level - 1) // 10) + 1 for level in levels}
        assert eras == {1, 2, 3, 4, 5, 6}, f"{industry} must have unlocks across all six eras: {eras}"

    assert validate_recipe_dag() is True, "expanded production chains must remain acyclic"

    print("NATBIRZHA progression catalog checks: PASS")


if __name__ == "__main__":
    run()
