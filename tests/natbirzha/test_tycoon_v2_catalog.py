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
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.business_investment import investment_curve
from backend.natbirzha.services.business_rates import resource_business_rates
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


def test_every_career_business_is_profitable_at_reference_market_prices() -> None:
    """Player-market reference prices define the investment return curve."""
    for spec in CAREER_BUSINESSES.values():
        rates = resource_business_rates(
            NatBusiness(stage=1, efficiency=1, health=100,
                base_maintenance_per_hour=spec["base_maintenance_per_hour"], metadata_json={}),
            spec, upgrading=False,
        )
        revenue = sum(
            float(quantity) * CANONICAL_ITEMS[item_id]["base_price"] * rates.output_multiplier
            for item_id, quantity in spec["outputs_per_hour"].items()
        )
        input_cost = sum(
            float(quantity) * CANONICAL_ITEMS[item_id]["base_price"] * rates.input_multiplier
            for item_id, quantity in spec["inputs_per_hour"].items()
        )
        profit_after_tax = (revenue - input_cost - rates.maintenance_per_hour) * (1 - nat_settings.TAX_RATE)
        assert profit_after_tax > 0, spec["id"]
        opening_capital = investment_curve(spec)[1]
        assert abs(opening_capital / profit_after_tax - spec["target_open_roi_hours"]) <= .05, spec["id"]


def test_water_demand_multiplier_preserves_price_and_target_return() -> None:
    for business_id in ("water_treatment", "deep_water_treatment"):
        spec = CAREER_BUSINESSES[business_id]
        assert spec["inputs_per_hour"].get("water", 0) > 0, business_id
        assert CANONICAL_ITEMS["water"]["base_price"] == 2
        assert spec["stage_rates"][1]["payback_hours"] == spec["target_open_roi_hours"]


def _career_profit_per_hour(spec: dict, stage: int) -> float:
    rates = resource_business_rates(
        NatBusiness(stage=stage, efficiency=1, health=100,
            base_maintenance_per_hour=spec["base_maintenance_per_hour"], metadata_json={}),
        spec, upgrading=False,
    )
    revenue = sum(
        float(quantity) * CANONICAL_ITEMS[item_id]["base_price"] * rates.output_multiplier
        for item_id, quantity in spec["outputs_per_hour"].items()
    )
    inputs = sum(
        float(quantity) * CANONICAL_ITEMS[item_id]["base_price"] * rates.input_multiplier
        for item_id, quantity in spec["inputs_per_hour"].items()
    )
    return (revenue - inputs - rates.maintenance_per_hour) * (1 - nat_settings.TAX_RATE)


def test_career_investment_has_ten_hour_start_and_compounding_upgrade_returns() -> None:
    ordered = sorted(
        (spec for spec in CAREER_BUSINESSES.values() if spec["specialization"] == "miner"),
        key=lambda spec: spec["industry_order"],
    )
    targets = [float(spec["target_open_roi_hours"]) for spec in ordered[:12]]
    assert targets[0] == 10
    assert all(left < right for left, right in zip(targets, targets[1:]))

    for spec in CAREER_BUSINESSES.values():
        target_roi = float(spec["target_open_roi_hours"])
        for stage in range(1, int(spec["max_stage"])):
            current_profit = _career_profit_per_hour(spec, stage)
            next_profit = _career_profit_per_hour(spec, stage + 1)
            quote = BusinessService.upgrade_quote(spec, stage)
            milestone_cost = sum(
                float(quantity) * CANONICAL_ITEMS[item_id]["base_price"]
                for item_id, quantity in (quote.get("milestone") or {}).get("resources", {}).items()
            )
            all_in_cost = float(quote["cost"]) + milestone_cost
            marginal_profit = next_profit - current_profit
            payback = all_in_cost / marginal_profit if marginal_profit > 0 else float("inf")
            assert marginal_profit > 0, (spec["id"], stage)
            assert payback <= target_roi, (spec["id"], stage, payback, target_roi)
        assert abs(
            investment_curve(spec)[1] / _career_profit_per_hour(spec, 1) - target_roi
        ) <= .05, spec["id"]
        assert abs(
            investment_curve(spec)[spec["max_stage"]]
            / _career_profit_per_hour(spec, spec["max_stage"])
            - 8.5
        ) <= .05, spec["id"]


def test_nonstarter_enterprises_require_cross_industry_opening_resources() -> None:
    starters = [spec for spec in CAREER_BUSINESSES.values() if spec["starter"]]
    nonstarters = [spec for spec in CAREER_BUSINESSES.values() if not spec["starter"]]
    assert len(starters) == len(INDUSTRIES)
    assert all(not spec["open_resources"] for spec in starters)
    assert all(spec["open_resources"] for spec in nonstarters)
