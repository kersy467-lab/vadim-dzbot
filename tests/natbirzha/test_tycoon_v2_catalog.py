"""Career catalog invariants for the server-owned NATBIRZHA 2.0 economy."""

from collections import Counter

from backend.natbirzha.catalogs.businesses import (
    BUSINESS_CATALOG,
    CAREER_BUSINESSES,
    INDUSTRIES,
    get_business_spec,
    starter_business_spec,
    validate_business_catalog,
    visible_business_specs,
)
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, get_npc_buy_price, get_npc_sell_price
from backend.natbirzha.services.business_service import BusinessService


def test_v2_catalog_contains_ten_long_industry_careers() -> None:
    counts = Counter(spec["specialization"] for spec in CAREER_BUSINESSES.values())
    assert set(counts) == set(INDUSTRIES)
    assert len(CAREER_BUSINESSES) >= 90
    assert min(counts.values()) >= 9
    assert counts["miner"] == 12
    assert BUSINESS_CATALOG["coal_open_pit"]["max_stage"] == 50
    assert BUSINESS_CATALOG["uranium_complex_v2"]["outputs_per_hour"]["uranium_raw"] > 0


def test_every_industry_has_exactly_one_visible_starter_and_localized_branch() -> None:
    for industry_id in INDUSTRIES:
        starter = starter_business_spec(industry_id)
        assert starter is not None and starter["specialization"] == industry_id
        visible = visible_business_specs(specialization=industry_id)
        assert visible and all(spec["specialization"] == industry_id for spec in visible)
        assert visible[0]["industry_order"] == 1
        assert visible[0]["starter"] is True


def test_career_catalog_only_references_canonical_resources() -> None:
    used: set[str] = set()
    for spec in CAREER_BUSINESSES.values():
        used.update(spec["inputs_per_hour"])
        used.update(spec["outputs_per_hour"])
        used.update(spec["open_resources"])
        for milestone in spec["milestones"].values():
            used.update(milestone.get("resources", {}))
    assert used <= set(CANONICAL_ITEMS)


def test_v2_catalog_has_valid_expensive_long_progression() -> None:
    assert validate_business_catalog() is True
    coal = get_business_spec("coal_open_pit")
    assert coal is BUSINESS_CATALOG["coal_open_pit"]
    assert get_business_spec("unknown") is None
    assert coal["upgrade_cost_growth"] > coal["output_growth"] > coal["input_growth"]
    assert set(coal["milestones"]) == {10, 20, 30, 40, 50}
    assert coal["milestones"][50]["label"] == "Автоматизированный угольный комплекс"


def test_every_career_business_is_viable_through_state_fallback() -> None:
    """NPC is a bad-price safety net, never an accidental permanent loss loop."""
    for spec in CAREER_BUSINESSES.values():
        revenue = sum(
            float(quantity) * get_npc_buy_price(item_id)
            for item_id, quantity in spec["outputs_per_hour"].items()
        )
        input_cost = sum(
            float(quantity) * get_npc_sell_price(item_id)
            for item_id, quantity in spec["inputs_per_hour"].items()
        )
        net = revenue - input_cost - float(spec["base_maintenance_per_hour"])
        assert net > 0, spec["id"]
        construction_cost = sum(
            float(quantity) * get_npc_sell_price(item_id)
            for item_id, quantity in spec["open_resources"].items()
        )
        actual_roi = (float(spec["open_cost"]) + construction_cost) / net
        target_roi = float(spec["target_open_roi_hours"])
        assert abs(actual_roi - target_roi) <= target_roi * 0.02, spec["id"]


def test_water_demand_multiplier_preserves_water_processor_fallback_margin() -> None:
    for business_id in ("water_treatment", "deep_water_treatment"):
        spec = CAREER_BUSINESSES[business_id]
        revenue = sum(
            float(quantity) * get_npc_buy_price(item_id)
            for item_id, quantity in spec["outputs_per_hour"].items()
        )
        input_cost = sum(
            float(quantity) * get_npc_sell_price(item_id)
            for item_id, quantity in spec["inputs_per_hour"].items()
        )
        net = revenue - input_cost - float(spec["base_maintenance_per_hour"])
        actual_roi = (float(spec["open_cost"]) + sum(
            float(quantity) * get_npc_sell_price(item_id)
            for item_id, quantity in spec["open_resources"].items()
        )) / net
        target_roi = float(spec["target_open_roi_hours"])
        assert net > 0, business_id
        assert abs(actual_roi - target_roi) <= target_roi * 0.02, business_id


def _career_profit_per_hour(spec: dict, stage: int) -> float:
    input_multiplier = float(spec["input_growth"]) ** (stage - 1)
    output_multiplier = float(spec["output_growth"]) ** (stage - 1)
    for milestone_stage, milestone in spec["milestones"].items():
        if stage >= int(milestone_stage):
            input_multiplier *= float(milestone.get("input_multiplier", 1.0))
            output_multiplier *= float(milestone.get("output_multiplier", 1.0))
    revenue = sum(
        float(quantity) * output_multiplier * get_npc_buy_price(item_id)
        for item_id, quantity in spec["outputs_per_hour"].items()
    )
    inputs = sum(
        float(quantity) * input_multiplier * get_npc_sell_price(item_id)
        for item_id, quantity in spec["inputs_per_hour"].items()
    )
    return revenue - inputs - float(spec["base_maintenance_per_hour"])


def test_career_investment_has_ten_hour_start_and_compounding_upgrade_returns() -> None:
    ordered = sorted(
        (spec for spec in CAREER_BUSINESSES.values() if spec["specialization"] == "miner"),
        key=lambda spec: spec["industry_order"],
    )
    targets = [float(spec["target_open_roi_hours"]) for spec in ordered[:12]]
    assert targets[0] == 10
    assert all(left < right for left, right in zip(targets, targets[1:]))

    for spec in CAREER_BUSINESSES.values():
        first_profit = _career_profit_per_hour(spec, 1)
        target_roi = float(spec["target_open_roi_hours"])
        for stage in range(1, int(spec["max_stage"])):
            current_profit = _career_profit_per_hour(spec, stage)
            next_profit = _career_profit_per_hour(spec, stage + 1)
            quote = BusinessService.upgrade_quote(spec, stage)
            milestone_cost = sum(
                float(quantity) * get_npc_sell_price(item_id)
                for item_id, quantity in (quote.get("milestone") or {}).get("resources", {}).items()
            )
            all_in_cost = float(quote["cost"]) + milestone_cost
            marginal_profit = next_profit - current_profit
            payback = all_in_cost / marginal_profit if marginal_profit > 0 else float("inf")
            assert marginal_profit > 0, (spec["id"], stage)
            assert payback <= target_roi, (spec["id"], stage, payback, target_roi)
        assert _career_profit_per_hour(spec, 10) >= first_profit * 2, spec["id"]


def test_nonstarter_enterprises_require_cross_industry_opening_resources() -> None:
    starters = [spec for spec in CAREER_BUSINESSES.values() if spec["starter"]]
    nonstarters = [spec for spec in CAREER_BUSINESSES.values() if not spec["starter"]]
    assert len(starters) == len(INDUSTRIES)
    assert all(not spec["open_resources"] for spec in starters)
    assert all(spec["open_resources"] for spec in nonstarters)
