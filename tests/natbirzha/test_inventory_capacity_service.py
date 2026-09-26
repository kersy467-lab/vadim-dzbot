from collections import defaultdict
from copy import copy
from math import isclose

from backend.natbirzha.catalogs.businesses import BUSINESS_CATALOG, get_business_spec
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.industry_upgrade_service import IndustryUpgradeService
from backend.natbirzha.services.inventory_capacity_service import InventoryCapacityService


def make_company(company_id=1, level=1, upgrades=None):
    return NatCompany(
        id=company_id,
        user_id=company_id,
        name=f"Company {company_id}",
        specialization="water",
        level=level,
        industry_upgrade_levels_json=upgrades or {},
        is_bankrupt=False,
    )


def make_business(business_type, *, company_id=1, business_id=1, stage=1,
                  status="ACTIVE", health=100, efficiency=1, specialization="water",
                  metadata=None):
    spec = get_business_spec(business_type)
    assert spec is not None
    return NatBusiness(
        id=business_id,
        company_id=company_id,
        business_type=business_type,
        specialization=specialization,
        stage=stage,
        status=status,
        health=health,
        efficiency=efficiency,
        base_maintenance_per_hour=spec["base_maintenance_per_hour"],
        metadata_json=metadata or {},
    )


def test_capacity_aggregates_stage_condition_asset_and_industry_adjusted_throughput():
    company = make_company(company_id=1, level=20, upgrades={"water": 3})
    businesses = [
        make_business(
            "regional_water_operator", business_id=1, stage=50, health=80,
            efficiency=.9, metadata={"asset_output_multiplier": 1.2},
        ),
        make_business(
            "regional_water_operator", business_id=2, stage=48, status="UPGRADING",
            health=60, efficiency=.7, metadata={"asset_output_multiplier": .5},
        ),
    ]

    expected_throughput = defaultdict(float)
    for business in businesses:
        spec = get_business_spec(business.business_type)
        rates = resource_business_rates(
            business,
            spec,
            upgrading=business.status == "UPGRADING",
            output_bonus_multiplier=IndustryUpgradeService.bonus_multiplier(
                company, business.specialization
            ),
        )
        next_stage_rates = None
        if business.status == "UPGRADING":
            next_stage = copy(business)
            next_stage.stage += 1
            next_stage_rates = resource_business_rates(
                next_stage, spec, upgrading=False,
                output_bonus_multiplier=IndustryUpgradeService.bonus_multiplier(
                    company, business.specialization
                ),
            )
        for item_id, rate in spec["outputs_per_hour"].items():
            multiplier = rates.output_multiplier
            if next_stage_rates is not None:
                multiplier = max(multiplier, next_stage_rates.output_multiplier)
            expected_throughput[item_id] += rate * multiplier

    capacities = InventoryCapacityService.capacity_by_item(company, businesses)
    horizon = IdleEconomyService.offline_cap_hours(company)
    assert horizon == 48
    for item_id, throughput_per_hour in expected_throughput.items():
        minimum = float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
        projected = throughput_per_hour * horizon
        expected = minimum + projected
        assert isclose(capacities[item_id], expected, rel_tol=1e-9)
        assert expected > nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM


def test_capacity_ignores_bankrupt_hidden_and_foreign_businesses():
    company = make_company(company_id=7)
    hidden_type = next(
        spec["id"] for spec in BUSINESS_CATALOG.values() if spec.get("legacy_hidden")
    )
    active = make_business("regional_water_operator", company_id=7, business_id=1)
    ignored = [
        make_business("regional_water_operator", company_id=7, business_id=2, status="BANKRUPT"),
        make_business("regional_water_operator", company_id=8, business_id=3),
        make_business(hidden_type, company_id=7, business_id=4),
    ]

    capacities = InventoryCapacityService.capacity_by_item(company, [active, *ignored])
    spec = get_business_spec(active.business_type)
    rates = resource_business_rates(active, spec, upgrading=False)
    horizon = IdleEconomyService.offline_cap_hours(company)
    expected = {
        item_id: (
            float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM)
            + quantity * rates.output_multiplier * horizon
        )
        for item_id, quantity in spec["outputs_per_hour"].items()
    }
    assert capacities.keys() == expected.keys()
    for item_id, capacity in expected.items():
        assert isclose(capacities[item_id], capacity, rel_tol=1e-9)


def test_configured_inventory_cap_is_a_minimum_allowance():
    company = make_company(company_id=9, level=1)
    business = make_business("regional_water_operator", company_id=9)

    capacities = InventoryCapacityService.capacity_by_item(company, [business])

    assert capacities
    spec = get_business_spec(business.business_type)
    rates = resource_business_rates(business, spec, upgrading=False)
    horizon = IdleEconomyService.offline_cap_hours(company)
    assert all(
        isclose(
            capacities[item_id],
            nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM
            + quantity * rates.output_multiplier * horizon,
        )
        for item_id, quantity in spec["outputs_per_hour"].items()
    )


def test_capacity_remains_dynamic_for_a_storage_paused_producer():
    company = make_company(company_id=10, level=20)
    business = make_business(
        "regional_water_operator", company_id=10, status="PAUSED_STORAGE", stage=50
    )
    capacities = InventoryCapacityService.capacity_by_item(company, [business])
    assert capacities["water"] > nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM
