from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.world_reset_service import WorldResetService


def test_world_reset_table_scope_preserves_only_reference_catalogs():
    tables = {table.name for table in WorldResetService.resettable_tables()}
    assert "users" not in tables
    assert "nat_companies" in tables
    assert "nat_inventory" in tables
    assert "nat_factories" in tables
    assert "nat_armies" in tables
    assert "nat_market_orders" in tables
    assert "nat_stocks" in tables
    assert "nat_premium_ledger" in tables
    assert "nat_creator_audit_logs" in tables
    assert "nat_state_treasury" in tables
    assert "nat_pve_corporations" not in tables
    assert "nat_reference_rate_snapshots" not in tables


def test_world_reset_confirmation_and_new_profile_grants():
    assert WorldResetService.CONFIRMATION_PHRASE == "СБРОСИТЬ НАТБИРЖУ"
    assert nat_settings.CREATOR_STARTING_CASH == 500_000
    assert nat_settings.CREATOR_STARTING_PVC == 200
    assert nat_settings.STARTING_CASH == 50_000
    assert nat_settings.TESTER_STARTING_PVC == 200
