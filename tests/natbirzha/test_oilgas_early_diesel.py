"""Early oil-to-diesel progression remains playable and calibrated."""

import asyncio
from math import isclose

from backend.natbirzha.api.business_routes import business_catalog
from backend.natbirzha.catalogs.businesses import (
    CAREER_BUSINESSES,
    REBIRTH_BUSINESSES,
    validate_business_catalog,
)
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.business_investment import investment_curve
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.models.business import NatBusiness


def test_starting_oil_well_does_not_require_diesel():
    well = CAREER_BUSINESSES["small_oil_well_v2"]

    assert "fuel_diesel" not in well["inputs_per_hour"]
    assert well["outputs_per_hour"].get("oil_crude", 0) > 0


def test_small_refinery_produces_diesel_and_buys_crude_before_level_16():
    refinery = CAREER_BUSINESSES["small_refinery_v2"]

    assert refinery["specialization"] == "oilman"
    assert refinery["mechanic"] == "resource_production"
    assert refinery["industry_order"] == 2
    assert refinery["company_level_required"] == 4
    assert refinery["inputs_per_hour"].get("oil_crude", 0) > 0
    assert refinery["outputs_per_hour"].get("fuel_diesel", 0) > 0
    assert "oil_field_v2" not in refinery["prerequisites"]
    assert validate_business_catalog()

    api_items = asyncio.run(business_catalog(specialization="oilman"))["items"]
    api_refinery = next(item for item in api_items if item["id"] == "small_refinery_v2")
    assert api_refinery["company_level_required"] == 4
    assert api_refinery["inputs_per_hour"].get("oil_crude", 0) > 0
    assert api_refinery["outputs_per_hour"].get("fuel_diesel", 0) > 0


def test_early_oil_progression_is_reported_by_the_economy_audit():
    from scripts.natbirzha_economy_audit import evaluate

    _, summary = evaluate()
    early = summary["early_oil_diesel_progression"]

    assert early["starter_diesel_input_per_hour"] == 0
    assert early["ordinary_crude_buyers_before_level_16"] == ["small_refinery_v2"]
    assert early["ordinary_diesel_producers_before_level_16"] == ["small_refinery_v2"]
    assert early["small_refinery_open_payback_hours"] <= early["small_refinery_target_open_roi_hours"]


def test_small_refinery_balance_is_calibrated_and_later_oil_progression_is_preserved():
    refinery = CAREER_BUSINESSES["small_refinery_v2"]
    profile = refinery["stage_rates"][1]
    capital = investment_curve(refinery)[1]
    business = NatBusiness(
        stage=1,
        efficiency=1,
        health=100,
        base_maintenance_per_hour=refinery["base_maintenance_per_hour"],
        metadata_json={},
    )
    rates = resource_business_rates(business, refinery, upgrading=False)
    revenue = sum(
        float(quantity) * CANONICAL_ITEMS[item_id]["base_price"]
        for item_id, quantity in refinery["outputs_per_hour"].items()
    ) * rates.output_multiplier
    expenses = sum(
        float(quantity) * CANONICAL_ITEMS[item_id]["base_price"]
        for item_id, quantity in refinery["inputs_per_hour"].items()
    ) * rates.input_multiplier + rates.maintenance_per_hour
    actual_payback = capital / ((revenue - expenses) * (1 - nat_settings.TAX_RATE))

    assert isclose(actual_payback, profile["payback_hours"], rel_tol=0.002)
    assert refinery["max_reference_expense_share_pct"] <= 45

    assert CAREER_BUSINESSES["refinery_v2"]["company_level_required"] == 16
    assert CAREER_BUSINESSES["diesel_complex_v2"]["company_level_required"] == 21
    rebirth = REBIRTH_BUSINESSES["rebirth_oilman_1"]
    assert rebirth["prerequisites"] == {"offshore_platform_v2": 10}
    assert "oil_crude" in rebirth["outputs_per_hour"]
    assert "gas_natural" in rebirth["outputs_per_hour"]
