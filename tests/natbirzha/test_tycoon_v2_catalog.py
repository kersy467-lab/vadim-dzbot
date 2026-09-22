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
        actual_roi = float(spec["open_cost"]) / net
        target_roi = float(spec["target_open_roi_hours"])
        assert actual_roi <= target_roi * 1.02, spec["id"]


def test_nonstarter_enterprises_require_cross_industry_opening_resources() -> None:
    starters = [spec for spec in CAREER_BUSINESSES.values() if spec["starter"]]
    nonstarters = [spec for spec in CAREER_BUSINESSES.values() if not spec["starter"]]
    assert len(starters) == len(INDUSTRIES)
    assert all(not spec["open_resources"] for spec in starters)
    assert all(spec["open_resources"] for spec in nonstarters)
