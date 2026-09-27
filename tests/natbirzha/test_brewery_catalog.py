from importlib import import_module
import pytest

from backend.natbirzha.catalogs.businesses.schema import REQUIRED_BUSINESS_SPEC_KEYS
from backend.natbirzha.models.inventory import CANONICAL_ITEMS


try:
    BREWERY_BUSINESSES = import_module(
        "backend.natbirzha.catalogs.businesses.brewery"
    ).BREWERY_BUSINESSES
except ModuleNotFoundError as exc:
    if exc.name != "backend.natbirzha.catalogs.businesses.brewery":
        raise
    BREWERY_BUSINESSES = None


def test_brewery_catalog_has_one_starter_and_ten_progressive_enterprises() -> None:
    assert BREWERY_BUSINESSES is not None, "brewery catalog module is missing"
    specs = list(BREWERY_BUSINESSES.values())

    assert len(specs) == 11
    assert [spec["industry_order"] for spec in specs] == list(range(1, 12))
    assert sum(bool(spec["starter"]) for spec in specs) == 1
    assert specs[0]["starter"] is True
    assert all(not spec["starter"] for spec in specs[1:])


def test_brewery_recipes_use_agricultural_inputs_and_progressive_outputs() -> None:
    assert BREWERY_BUSINESSES is not None, "brewery catalog module is missing"
    specs = sorted(BREWERY_BUSINESSES.values(), key=lambda spec: spec["industry_order"])

    for spec in specs[:3]:
        assert spec["outputs_per_hour"].keys() == {"beer"}
        assert spec["inputs_per_hour"].get("grain", 0) > 0
        assert spec["inputs_per_hour"].get("hops", 0) > 0
        assert spec["inputs_per_hour"].get("energy", 0) > 0
        assert spec["inputs_per_hour"].get("water", 0) > 0

    for spec in specs[3:6]:
        assert spec["outputs_per_hour"].keys() == {"wine"}
        assert spec["inputs_per_hour"].get("grapes", 0) > 0
        assert spec["inputs_per_hour"].get("energy", 0) > 0
        assert spec["inputs_per_hour"].get("water", 0) > 0

    for spec in specs[6:]:
        assert spec["outputs_per_hour"].keys() == {"aged_spirits"}
        assert spec["inputs_per_hour"].get("wine", 0) > 0
        assert spec["inputs_per_hour"].get("energy", 0) > 0
        assert spec["inputs_per_hour"].get("water", 0) > 0


def test_brewery_catalog_entries_follow_the_shared_business_schema() -> None:
    assert BREWERY_BUSINESSES is not None, "brewery catalog module is missing"
    all_items = set(CANONICAL_ITEMS)

    for business_id, spec in BREWERY_BUSINESSES.items():
        assert set(spec) >= REQUIRED_BUSINESS_SPEC_KEYS, business_id
        assert spec["id"] == business_id
        assert spec["specialization"] == "brewery"
        assert spec["max_stage"] == 50
        assert set(spec["milestones"]) == {10, 20, 30, 40, 50}
        assert spec["industry_order"] >= 1
        assert spec["open_cost"] > 0
        assert spec["inputs_per_hour"] and spec["outputs_per_hour"]
        assert all(quantity > 0 for quantity in spec["inputs_per_hour"].values())
        assert all(quantity > 0 for quantity in spec["outputs_per_hour"].values())

        used_items = set(spec["inputs_per_hour"]) | set(spec["outputs_per_hour"])
        used_items |= set(spec["open_resources"])
        for milestone in spec["milestones"].values():
            used_items |= set(milestone.get("resources", {}))
        assert used_items <= all_items, (business_id, used_items - all_items)

    specs = sorted(BREWERY_BUSINESSES.values(), key=lambda spec: spec["industry_order"])
    for previous, current in zip(specs, specs[1:]):
        assert set(current["prerequisites"]) == {previous["id"]}
        assert 1 <= current["prerequisites"][previous["id"]] <= 50


def test_brewery_starter_matches_employee_beer_demand_across_other_starters() -> None:
    from backend.natbirzha.catalogs.businesses import (
        INDUSTRIES,
        CAREER_BUSINESSES,
        starter_business_spec,
        validate_business_catalog,
    )
    assert validate_business_catalog()
    assert len(INDUSTRIES) == 12
    assert "forester" in INDUSTRIES and "brewery" in INDUSTRIES
    assert all(starter_business_spec(industry) for industry in INDUSTRIES)

    beer_demand = 0.0
    for industry_id in INDUSTRIES:
        spec = starter_business_spec(industry_id)
        stage_one = spec["stage_rates"][1]
        if industry_id == "brewery":
            assert "beer" not in spec["inputs_per_hour"]
            continue
        beer_rate = spec["inputs_per_hour"].get("beer", 0.0) * stage_one["input"]
        assert beer_rate > 0, industry_id
        beer_demand += beer_rate

    brewery = starter_business_spec("brewery")
    stage_one = brewery["stage_rates"][1]
    beer_supply = brewery["outputs_per_hour"]["beer"] * stage_one["output"]
    # Replacing the old, lower-value forestry starter with AI compute raises
    # the employee-beverage demand budget; starter brewing now has a 30% buffer.
    assert beer_supply / beer_demand == pytest.approx(1.30, abs=0.01)

    # The beermaking starter has a modest first level price after unlocking;
    # full-stage profitability remains part of the same calibrated catalog.
    assert brewery["open_cost"] == 2_000
    assert set(CAREER_BUSINESSES) >= {spec["id"] for spec in BREWERY_BUSINESSES.values()}
