"""The same small worker beverage input applies to each non-brewery industry."""

from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.employee_beverage_inputs import add_employee_beverage_input


def test_first_three_businesses_consume_only_beer():
    output = {"steel": 100.0}
    for order in (1, 2, 3):
        inputs = add_employee_beverage_input(
            {"energy": 8.0}, output, specialization="metallurgist", order=order
        )
        assert inputs["beer"] > 0
        assert "wine" not in inputs
        assert "aged_spirits" not in inputs
        assert inputs["energy"] == 8.0
        beverage_cost = inputs["beer"] * CANONICAL_ITEMS["beer"]["base_price"]
        output_value = CANONICAL_ITEMS["steel"]["base_price"] * 100.0
        assert abs(beverage_cost / output_value - 0.01) < 1e-9


def test_later_businesses_progress_to_wine_then_elite_spirits():
    for order in (4, 8):
        inputs = add_employee_beverage_input(
            {}, {"electronics": 10.0}, specialization="technoprom", order=order
        )
        assert inputs.get("wine", 0) > 0
        assert "beer" not in inputs
        assert "aged_spirits" not in inputs

    late = add_employee_beverage_input(
        {}, {"ai_accelerator": 2.0}, specialization="technoprom", order=9
    )
    assert late.get("aged_spirits", 0) > 0
    assert "beer" not in late
    assert "wine" not in late


def test_brewery_does_not_consume_its_own_product_as_staff_supply():
    inputs = add_employee_beverage_input(
        {"hops": 2.0}, {"beer": 20.0}, specialization="brewery", order=1
    )
    assert inputs == {"hops": 2.0}


def test_real_catalogs_budget_exactly_one_percent_for_staff_beverages():
    from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES, INDUSTRIES

    beverage_ids = {"beer", "wine", "aged_spirits"}
    measured = 0
    phases_by_industry = {industry: set() for industry in INDUSTRIES if industry != "brewery"}
    for spec in CAREER_BUSINESSES.values():
        if spec["specialization"] == "brewery":
            continue
        order = spec["industry_order"]
        expected_beverage = "beer" if order <= 3 else "wine" if order <= 8 else "aged_spirits"
        assert spec["inputs_per_hour"].get(expected_beverage, 0) > 0, spec["id"]
        assert not (set(spec["inputs_per_hour"]) & (beverage_ids - {expected_beverage})), spec["id"]
        phases_by_industry[spec["specialization"]].add(expected_beverage)
        stage_one = spec["stage_rates"][1]
        beverage_cost = sum(
            quantity * stage_one["input"] * CANONICAL_ITEMS[item_id]["base_price"]
            for item_id, quantity in spec["inputs_per_hour"].items()
            if item_id in beverage_ids
        )
        if beverage_cost <= 0:
            continue
        output_value = sum(
            quantity * stage_one["output"] * CANONICAL_ITEMS[item_id]["base_price"]
            for item_id, quantity in spec["outputs_per_hour"].items()
        )
        share = beverage_cost / output_value
        assert 0.0099 <= share <= 0.0101, (spec["id"], share)
        measured += 1

    assert measured >= 100
    assert all(phases == beverage_ids for phases in phases_by_industry.values())


def test_agriculture_supplies_hops_for_beer_and_grapes_for_wine():
    from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES

    agricultural_outputs = [
        (spec["industry_order"], spec["outputs_per_hour"])
        for spec in CAREER_BUSINESSES.values()
        if spec["specialization"] == "agrarian"
    ]
    assert any(order <= 3 and outputs.get("hops", 0) > 0 for order, outputs in agricultural_outputs)
    assert any(order <= 11 and outputs.get("grapes", 0) > 0 for order, outputs in agricultural_outputs)
