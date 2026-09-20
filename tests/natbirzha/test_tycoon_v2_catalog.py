"""Business catalog invariants for the server-owned V2 economy."""

from backend.natbirzha.catalogs.businesses import BUSINESS_CATALOG, get_business_spec, validate_business_catalog


def test_v2_catalog_contains_distinct_starter_and_industry_businesses() -> None:
    assert BUSINESS_CATALOG["retail_chain"]["max_stage"] == 20
    assert BUSINESS_CATALOG["retail_chain"]["open_cost"] == 8_000
    assert BUSINESS_CATALOG["energy_company"]["outputs_per_hour"] == {"energy": 8.0}
    assert BUSINESS_CATALOG["agroholding"]["inputs_per_hour"] == {"water": 0.5, "energy": 0.25}
    assert BUSINESS_CATALOG["logistics_company"]["mechanic"] == "fleet"
    assert BUSINESS_CATALOG["it_company"]["mechanic"] == "employees_projects"


def test_v2_catalog_has_one_valid_server_spec_per_business_type() -> None:
    assert validate_business_catalog() is True
    assert get_business_spec("retail_chain") is BUSINESS_CATALOG["retail_chain"]
    assert get_business_spec("unknown") is None
    assert len(BUSINESS_CATALOG) >= 14


def test_business_catalog_uses_expensive_late_stage_progression() -> None:
    retail = BUSINESS_CATALOG["retail_chain"]
    assert retail["upgrade_cost_growth"] > retail["income_growth"]
    assert retail["milestones"][5]["label"] == "Районная сеть"
