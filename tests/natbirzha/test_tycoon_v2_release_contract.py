"""Pure release-contract checks for the NATBIRZHA 2.0 tycoon rewrite."""

from pathlib import Path

from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES, INDUSTRIES
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.config import nat_settings


ROOT = Path(__file__).resolve().parents[2]


def test_career_graph_is_ordered_and_reachable() -> None:
    by_id = CAREER_BUSINESSES
    for spec in by_id.values():
        assert spec["max_stage"] == 50
        assert set(spec["milestones"]) == {10, 20, 30, 40, 50}
        assert spec["name"] and "_" not in spec["name"]
        assert spec["description"]
        for dependency_id, required_stage in spec["prerequisites"].items():
            dependency = by_id[dependency_id]
            assert dependency["specialization"] == spec["specialization"]
            assert dependency["industry_order"] < spec["industry_order"]
            assert 1 <= required_stage <= 50


def test_every_career_resource_is_localized_and_known() -> None:
    known = set(CANONICAL_ITEMS)
    for spec in CAREER_BUSINESSES.values():
        used = set(spec["inputs_per_hour"]) | set(spec["outputs_per_hour"]) | set(spec["open_resources"])
        for milestone in spec["milestones"].values():
            used |= set(milestone.get("resources", {}))
        assert used <= known, spec["id"]


def test_industry_catalog_shape_matches_game_design() -> None:
    for industry_id in INDUSTRIES:
        branch = sorted(
            (spec for spec in CAREER_BUSINESSES.values() if spec["specialization"] == industry_id),
            key=lambda spec: spec["industry_order"],
        )
        assert len(branch) >= 9
        assert branch[0]["starter"] is True
        assert branch[0]["industry_order"] == 1
        assert all(not spec["starter"] for spec in branch[1:])
        assert all(spec["open_resources"] for spec in branch[1:])
    assert len([s for s in CAREER_BUSINESSES.values() if s["specialization"] == "miner"]) == 12


def test_tax_contract_matches_requested_rules() -> None:
    assert float(nat_settings.TAX_RATE) == 0.13
    assert int(nat_settings.TAX_GRACE_DAYS) == 3
    assert float(nat_settings.TAX_DAILY_PENALTY_RATE) == 0.50


def test_frontend_enforces_industry_branch_and_tax_navigation() -> None:
    tycoon = (ROOT / "frontend/natbirzha/js/screens/tycoon.js").read_text(encoding="utf-8")
    market = (ROOT / "frontend/natbirzha/js/screens/market.js").read_text(encoding="utf-8")
    onboarding = (ROOT / "frontend/natbirzha/js/screens/onboarding.js").read_text(encoding="utf-8")
    assert ".filter((item) => item.specialization === specialization)" in tycoon
    assert "Ваша отрасль — отдельная карьерная ветка" in tycoon
    assert "Каждые ${business.resource_tick_minutes || 15} мин" in tycoon
    assert 'data-section="tax"' in market and "renderTaxSection" in market
    assert "company-count" in onboarding and "status_color" in onboarding


def test_hard_reset_covers_new_v2_state() -> None:
    reset = (ROOT / "backend/natbirzha/services/company_reset_v2.py").read_text(encoding="utf-8")
    for model_name in (
        "NatBusiness", "NatBusinessSupplyPolicy", "NatBusinessVehicle", "NatBusinessEmployee",
        "NatBusinessProject", "NatBusinessIncomeDaily", "NatTaxDaily",
        "NatMilitaryInfrastructure", "NatArmyTraining",
    ):
        assert model_name in reset
