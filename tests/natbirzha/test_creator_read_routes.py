import asyncio
from types import SimpleNamespace

from backend.natbirzha.api import creator_routes
from backend.natbirzha.api import creator_economy_routes
from backend.natbirzha.services.creator_service import CreatorService
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


class DummySession:
    async def commit(self):
        return None


def test_creator_bonds_route_returns_frontend_contract(monkeypatch):
    bonds = [{"id": 1, "title": "Test bond"}]

    async def get_bonds(_session):
        return bonds

    monkeypatch.setattr(CreatorService, "get_bonds", get_bonds)

    result = asyncio.run(creator_routes.list_bonds(_admin=object(), session=object()))

    assert result == {"bonds": bonds}


def test_creator_premium_ledger_route_returns_frontend_contract(monkeypatch):
    entries = [{"id": 1, "amount": 25}]

    async def get_premium_ledger(_session, *, limit=100, company_id=None):
        return entries

    monkeypatch.setattr(CreatorService, "get_premium_ledger", get_premium_ledger)

    result = asyncio.run(creator_routes.get_premium_ledger(_admin=object(), session=object()))

    assert result == {"entries": entries}


def test_creator_audit_route_returns_frontend_contract(monkeypatch):
    logs = [{"id": 1, "action": "TEST"}]

    async def get_audit_log(_session, limit=50):
        return logs

    monkeypatch.setattr(CreatorService, "get_audit_log", get_audit_log)

    result = asyncio.run(creator_routes.get_audit_log(_admin=object(), session=object()))

    assert result == {"logs": logs}


def test_creator_economy_metrics_route_uses_existing_service(monkeypatch):
    summary = {"window_days": 7, "events": 0}

    async def get_summary(_session, *, days=7):
        return summary

    monkeypatch.setattr(EconomyMetricsService, "summary", get_summary)

    result = asyncio.run(creator_routes.get_economy_metrics(days=7, _admin=object(), session=object()))

    assert result == summary


def test_creator_state_economy_route_returns_snapshot(monkeypatch):
    snapshot = {"treasury_cash": 10_000_000_000_000, "default_mode": False, "stock": []}

    async def get_snapshot(_session):
        return snapshot

    monkeypatch.setattr(creator_economy_routes.StateEconomyService, "creator_snapshot", get_snapshot)
    result = asyncio.run(creator_economy_routes.get_state_economy(_admin=object(), session=object()))
    assert result == snapshot


def test_creator_state_foreign_export_toggle_audits_actor(monkeypatch):
    expected = {"foreign_exports_enabled": True}
    captured = {}

    async def set_exports(_session, *, enabled, actor_id):
        captured.update(enabled=enabled, actor_id=actor_id)
        return expected

    monkeypatch.setattr(creator_economy_routes.StateEconomyService, "set_foreign_exports_enabled", set_exports)
    actor = SimpleNamespace(tg_id=991_234)
    request = creator_economy_routes.ForeignExportsRequest(enabled=True)
    result = asyncio.run(creator_economy_routes.set_state_foreign_exports(
        request, admin=actor, session=DummySession()
    ))
    assert result == expected
    assert captured == {"enabled": True, "actor_id": 991_234}


def test_creator_market_route_uses_existing_snapshot(monkeypatch):
    snapshot = {"orders": [], "restrictions": [], "warnings": []}

    async def get_market_snapshot(_session):
        return snapshot

    monkeypatch.setattr(CreatorService, "get_market_snapshot", get_market_snapshot)

    result = asyncio.run(creator_routes.get_market(_admin=object(), session=object()))

    assert result == snapshot


def test_creator_warning_route_passes_actor_id(monkeypatch):
    expected = {"success": True, "warning_id": 4, "company_id": 9}
    captured = {}

    async def add_warning(_session, actor_id, company_id, reason, commit=True):
        captured.update(actor_id=actor_id, company_id=company_id, reason=reason, commit=commit)
        return expected

    monkeypatch.setattr(CreatorService, "add_warning", add_warning)
    actor = SimpleNamespace(id=2, tg_id=1234)
    request = creator_routes.WarningRequest(company_id=9, reason="Test warning")

    result = asyncio.run(creator_routes.send_warning(
        request, idempotency_key=None, admin=actor, session=DummySession()
    ))

    assert result == expected
    assert captured == {"actor_id": 1234, "company_id": 9, "reason": "Test warning", "commit": False}


def test_creator_restriction_route_passes_actor_id(monkeypatch):
    expected = {"success": True, "restriction_id": 5}
    captured = {}

    async def set_restriction(_session, actor_id, company_id, item_id, min_price, max_price, reason, duration_minutes, commit=True):
        captured.update(actor_id=actor_id, company_id=company_id, item_id=item_id, reason=reason, commit=commit)
        return expected

    monkeypatch.setattr(CreatorService, "set_restriction", set_restriction)
    actor = SimpleNamespace(id=2, tg_id=1234)
    request = creator_routes.RestrictionRequest(item_id="water", min_price=10, reason="Test restriction")

    result = asyncio.run(creator_routes.add_restriction(
        request, idempotency_key=None, admin=actor, session=DummySession()
    ))

    assert result == expected
    assert captured == {"actor_id": 1234, "company_id": None, "item_id": "water", "reason": "Test restriction", "commit": False}


def test_creator_remove_restriction_route_passes_actor_id(monkeypatch):
    expected = {"success": True, "removed_id": 5}
    captured = {}

    async def remove_restriction(_session, actor_id, restriction_id, commit=True):
        captured.update(actor_id=actor_id, restriction_id=restriction_id, commit=commit)
        return expected

    monkeypatch.setattr(CreatorService, "remove_restriction", remove_restriction)
    actor = SimpleNamespace(id=2, tg_id=1234)

    result = asyncio.run(creator_routes.remove_restriction(
        5, idempotency_key=None, admin=actor, session=DummySession()
    ))

    assert result == expected
    assert captured == {"actor_id": 1234, "restriction_id": 5, "commit": False}


def test_creator_issue_bond_route_uses_existing_service_and_actor(monkeypatch):
    expected = {"bond_id": 6, "raised_funds": 0}
    captured = {}

    async def issue_bonds(_session, actor_id, title, volume, face_value, coupon_rate, maturity_days, purpose, coupon_interval_days=None, commit=True):
        captured.update(actor_id=actor_id, title=title, volume=volume, purpose=purpose, commit=commit)
        return expected

    monkeypatch.setattr(CreatorService, "issue_bonds", issue_bonds)
    actor = SimpleNamespace(id=2, tg_id=1234)
    request = creator_routes.IssueBondRequest(
        title="Test bond", volume=10, face_value=100, coupon_rate=5, maturity_days=30, purpose="Testing"
    )

    result = asyncio.run(creator_routes.issue_bond(
        request, idempotency_key=None, admin=actor, session=DummySession()
    ))

    assert result == expected
    assert captured == {"actor_id": 1234, "title": "Test bond", "volume": 10, "purpose": "Testing", "commit": False}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main(["-q", "-p", "no:cacheprovider", __file__]))
