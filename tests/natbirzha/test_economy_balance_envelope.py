"""Economic contracts tested against the rates used by lazy settlement."""
from collections import defaultdict
from math import isclose, isfinite

from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.business_investment import investment_curve
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.business_service import BusinessService


def value(entries):
    return sum(float(q) * CANONICAL_ITEMS[k]["base_price"] for k, q in entries.items())


def rate(spec, stage):
    business = NatBusiness(stage=stage, efficiency=1, health=100,
        base_maintenance_per_hour=spec["base_maintenance_per_hour"], metadata_json={})
    return resource_business_rates(business, spec, upgrading=False)


def net_profit(spec, stage):
    actual = rate(spec, stage)
    revenue = value(spec["outputs_per_hour"]) * actual.output_multiplier
    inputs = value(spec["inputs_per_hour"]) * actual.input_multiplier
    return (revenue - inputs - actual.maintenance_per_hour) * (1 - nat_settings.TAX_RATE)


def test_upgrades_keep_material_demand_and_save_no_more_than_25_percent():
    for spec in CAREER_BUSINESSES.values():
        base, advanced = rate(spec, 1), rate(spec, spec["max_stage"])
        # Some renewable/utility businesses have no physical input recipe.
        if not spec["inputs_per_hour"]:
            continue
        relative_consumption = (
            advanced.input_multiplier / advanced.output_multiplier
        ) / (base.input_multiplier / base.output_multiplier)
        assert .74 <= relative_consumption <= 1, (spec["id"], relative_consumption)


def test_logistics_capacity_is_used_in_other_industries_expansion():
    producers = [
        spec for spec in CAREER_BUSINESSES.values()
        if "logistics_capacity" in spec["outputs_per_hour"]
    ]
    consumers = [
        spec for spec in CAREER_BUSINESSES.values()
        if spec["specialization"] != "logistics" and (
            "logistics_capacity" in spec["open_resources"]
            or any("logistics_capacity" in m.get("resources", {}) for m in spec["milestones"].values())
        )
    ]
    assert producers, "Logistics businesses must produce transport capacity"
    assert consumers, "Non-logistics industries must consume transport capacity during expansion"


def test_each_stage_matches_its_server_side_capital_payback_curve():
    full_stage_returns = defaultdict(list)
    for spec in CAREER_BUSINESSES.values():
        capital = investment_curve(spec)
        previous_profit = 0.0
        previous_payback = float("inf")
        for stage in range(1, spec["max_stage"] + 1):
            expected_payback = float(spec["stage_rates"][stage]["payback_hours"])
            profit = net_profit(spec, stage)
            actual_payback = capital[stage] / profit
            assert isfinite(profit) and profit > previous_profit, (spec["id"], stage, profit)
            assert isclose(actual_payback, expected_payback, rel_tol=.002), (
                spec["id"], stage, actual_payback, expected_payback
            )
            assert actual_payback <= previous_payback + 1e-6, (
                spec["id"], stage, actual_payback, previous_payback
            )
            if stage == 1:
                assert isclose(actual_payback, float(spec["target_open_roi_hours"]), rel_tol=.002)
            if stage == spec["max_stage"]:
                full_stage_returns[spec["specialization"]].append(100 / actual_payback)
            previous_profit = profit
            previous_payback = actual_payback

    medians = {
        industry: sorted(values)[len(values) // 2]
        for industry, values in full_stage_returns.items()
    }
    assert all(7 <= value <= 14 for value in medians.values()), medians
    assert max(medians.values()) / min(medians.values()) <= 1.01, medians


def test_upgrade_quotes_match_the_investment_curve():
    for spec in CAREER_BUSINESSES.values():
        capital = investment_curve(spec)
        for stage in range(1, spec["max_stage"]):
            quote = BusinessService.upgrade_quote(spec, stage)
            next_capital = capital[stage] + quote["cost"] + value(
                (quote.get("milestone") or {}).get("resources", {})
            )
            assert isclose(next_capital, capital[stage + 1], rel_tol=.002), (
                spec["id"], stage
            )


def test_economy_audit_reports_output_inventory_fill_horizon():
    from scripts.natbirzha_economy_audit import evaluate

    rows, summary = evaluate()
    cap_report = summary["output_inventory_cap"]
    stage_50 = cap_report["stages"]["50"]

    assert cap_report["units_per_item"] == 1_000_000
    assert cap_report["horizon_hours"] == 24
    assert "offline settlement horizon" in cap_report["policy"]
    assert stage_50["businesses_total"] == 108
    assert stage_50["businesses_filling_any_output"] == 0
    assert stage_50["output_items_filling_cap"] == 0
    assert stage_50["fill_by_horizon_hours"] == {
        "24": {"businesses_filling_any_output": 0, "output_items_filling_cap": 0},
        "48": {"businesses_filling_any_output": 0, "output_items_filling_cap": 0},
        "72": {"businesses_filling_any_output": 0, "output_items_filling_cap": 0},
        "168": {"businesses_filling_any_output": 0, "output_items_filling_cap": 0},
    }

    water = next(
        row for row in rows
        if row["business"] == "regional_water_operator" and row["stage"] == 50
    )
    assert water["first_output_to_fill_inventory_cap"] == "water"
    assert isclose(
        water["hours_to_fill_first_output_inventory_cap"],
        24 + 1_000_000 / 25_968_138.904450852,
        rel_tol=1e-7,
    )
    assert water["fills_output_inventory_cap_within_base_offline_horizon"] is False

    assert "theoretical" in summary["roi_basis"].lower()
    assert "all output can be sold" in summary["roi_basis"]
    assert all("theoretical" in row["roi_basis"].lower() for row in rows)
    assert summary["loss_making_npc"] == 110
    assert summary["npc_loss_scenario"]["loss_making_stage_rows"] == 110
    assert "unlimited npc spread stress scenario" in summary["npc_loss_scenario"]["basis"].lower()
    assert "ignores npc_daily_buyback_cash_limit" in summary["npc_loss_scenario"]["basis"].lower()
    assert summary["no_gameplay_consumer"] == []
    assert set(summary["project_or_army_only_sinks"]) == set(summary["no_industrial_consumer"])
    assert "one-time openings" in summary["flow_basis"].lower()
