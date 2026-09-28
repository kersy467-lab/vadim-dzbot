"""Transactional city-order cycle, escrow and delivery invariants."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES, INDUSTRIES, starter_business_spec
from backend.natbirzha.config import game_dt_iso
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory
from backend.natbirzha.models.market import NatMarketTrade
from backend.natbirzha.models.tax import NatCompanyProfitPeriod
from backend.natbirzha.services.city_order_service import CityOrderService


async def _fixture(treasury_cash: float = 10_000_000.0):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        users = [
            User(tg_id=991401, full_name="Supplier One"),
            User(tg_id=991402, full_name="Supplier Two"),
        ]
        session.add_all(users)
        await session.flush()
        companies = [
            NatCompany(user_id=users[0].id, name="Supplier One Co", specialization="miner", cash=1_000),
            NatCompany(user_id=users[1].id, name="Supplier Two Co", specialization="miner", cash=1_000),
        ]
        session.add_all(companies)
        session.add(NatStateTreasury(id=1, cash=treasury_cash))
        await session.commit()
        company_ids = [company.id for company in companies]
    return engine, sessions, company_ids


def _active_industries() -> list[str]:
    catalog_industries = {
        spec["specialization"] for spec in CAREER_BUSINESSES.values()
        if not spec.get("legacy_hidden")
    }
    return sorted(set(INDUSTRIES).intersection(catalog_industries))


def test_cycle_issues_every_catalog_industry_once_and_keeps_two_orders_live() -> None:
    async def check() -> None:
        engine, sessions, _companies = await _fixture()
        start = datetime(2026, 9, 26, 12, 0)
        expected_industries = set(_active_industries())
        assert expected_industries
        try:
            issued = []
            async with sessions() as session:
                for slot in range(len(expected_industries)):
                    result = await CityOrderService.issue_due(
                        session, now=start + timedelta(minutes=30 * slot)
                    )
                    assert result["created"] is True
                    issued.append(result["order"])
                await session.commit()

                assert {row["industry"] for row in issued} == expected_industries
                assert len({row["industry"] for row in issued}) == len(expected_industries)
                assert len({row["scheduled_slot"] for row in issued}) == len(issued)

                # Re-running one scheduler slot must not issue a duplicate.
                replay = await CityOrderService.issue_due(session, now=start)
                assert replay["created"] is False

                # Half-hour cadence and one-hour TTL imply no more than two open orders.
                for slot in range(len(expected_industries) + 1):
                    await CityOrderService.issue_due(
                        session, now=start + timedelta(minutes=30 * slot)
                    )
                    await session.flush()
                    open_count = await CityOrderService.count_open_orders(
                        session, now=start + timedelta(minutes=30 * slot)
                    )
                    assert open_count <= 2
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_missed_slots_create_only_one_current_order_and_do_not_skip_industry() -> None:
    async def check() -> None:
        engine, sessions, _companies = await _fixture()
        start = datetime(2026, 9, 26, 12, 0)
        try:
            async with sessions() as session:
                first = await CityOrderService.issue_due(session, now=start)
                resumed_at = start + timedelta(hours=2, minutes=7)
                resumed = await CityOrderService.issue_due(session, now=resumed_at)
                same_slot = await CityOrderService.issue_due(
                    session, now=resumed_at + timedelta(minutes=4)
                )
                await session.commit()

                assert first["created"] is True and resumed["created"] is True
                assert same_slot["created"] is False
                rows = (await session.execute(select(CityOrderService.order_model))).scalars().all()
                assert len(rows) == 2
                assert resumed["order"]["issued_at"] == game_dt_iso(resumed_at)
                assert resumed["order"]["expires_at"] == game_dt_iso(resumed_at + timedelta(hours=1))
                assert resumed["order"]["industry"] != first["order"]["industry"]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_new_catalog_industry_joins_saved_cycle_without_repeating_issued_industry(monkeypatch) -> None:
    """A sector added while a cycle is in progress joins its remaining queue."""
    async def check() -> None:
        engine, sessions, _companies = await _fixture()
        start = datetime(2026, 9, 26, 12, 0)
        try:
            async with sessions() as session:
                first = await CityOrderService.issue_due(session, now=start)
                added = "brewery_test_sector"
                monkeypatch.setitem(INDUSTRIES, added, {"name": "Test Brewery"})
                monkeypatch.setitem(CAREER_BUSINESSES, "brewery_test_opening", {
                    **CAREER_BUSINESSES[next(iter(CAREER_BUSINESSES))],
                    "id": "brewery_test_opening",
                    "specialization": added,
                    "starter": True,
                    "legacy_hidden": False,
                    "outputs_per_hour": {"grain": 1.0},
                })
                monkeypatch.setattr(
                    "backend.natbirzha.services.city_order_rates.starter_business_spec",
                    lambda industry: {
                        **CAREER_BUSINESSES["brewery_test_opening"],
                        "specialization": industry,
                    } if industry == added else starter_business_spec(industry),
                )
                issued = [first["order"]["industry"]]
                for slot in range(1, len(_active_industries())):
                    result = await CityOrderService.issue_due(
                        session, now=start + timedelta(minutes=30 * slot)
                    )
                    assert result["created"] is True
                    issued.append(result["order"]["industry"])
                await session.commit()
                assert len(issued) == len(set(issued))
                assert set(issued) == set(_active_industries())
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_order_quantity_uses_active_output_or_starter_and_shrinks_to_treasury() -> None:
    async def check() -> None:
        engine, sessions, _companies = await _fixture(treasury_cash=1.005)
        start = datetime(2026, 9, 26, 12, 0)
        try:
            async with sessions() as session:
                result = await CityOrderService.issue_due(session, now=start)
                assert result["created"] is True
                order = result["order"]
                price = Decimal(str(CANONICAL_ITEMS[order["item_id"]]["base_price"]))
                treasury = await session.get(NatStateTreasury, 1)
                assert order["unit_price"] == float(price * Decimal("1.20"))
                assert Decimal(str(order["reserved_cash"])) <= Decimal("1.00")
                assert Decimal(str(treasury.cash)) >= 0
                assert order["quantity"] > 0
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_ai_city_order_pays_market_reference_plus_twenty_percent(monkeypatch) -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        now = datetime(2026, 9, 26, 12, 0)
        try:
            monkeypatch.setattr(
                "backend.natbirzha.services.city_order_service.active_city_order_industries",
                lambda: ["ai_data"],
            )
            monkeypatch.setattr(
                "backend.natbirzha.services.city_order_service.primary_output",
                lambda _industry: (
                    "ai_compute",
                    {"outputs_per_hour": {"ai_compute": 160.0}},
                ),
            )

            async def output_rate(_session, _industry, _item_id, _starter):
                return 160.0

            monkeypatch.setattr(
                "backend.natbirzha.services.city_order_service.sector_output_rate",
                output_rate,
            )

            async with sessions() as session:
                result = await CityOrderService.issue_due(session, now=now)
                order = result["order"]
                assert order["item_id"] == "ai_compute"
                assert order["quantity"] == pytest.approx(80.0)
                assert order["unit_price"] == pytest.approx(90.0)
                assert order["reserved_cash"] == pytest.approx(7_200.0)

                session.add(NatInventory(
                    company_id=company_ids[0], item_id="ai_compute", quantity=80.0,
                    avg_cost_basis=65.0,
                ))
                await session.flush()
                payout = await CityOrderService.deliver(
                    session, company_ids[0], order["id"], 80.0,
                    idempotency_key="ai-city-order-80",
                    now=now + timedelta(minutes=1),
                )
                assert payout["cash_amount"] == pytest.approx(7_200.0)
                company = await session.get(NatCompany, company_ids[0])
                assert company.cash == pytest.approx(8_200.0)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_partial_deliveries_are_idempotent_taxed_and_bounded_by_available_stock() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        start = datetime(2026, 9, 26, 12, 0)
        try:
            async with sessions() as session:
                order_result = await CityOrderService.issue_due(session, now=start)
                assert order_result["created"] is True
                order = order_result["order"]
                item_id = order["item_id"]
                total_qty = order["quantity"]
                partial_qty = round(total_qty / 4, 6)
                assert 0 < partial_qty < total_qty
                sellers = (await session.execute(
                    select(NatCompany).where(NatCompany.id.in_(company_ids)).order_by(NatCompany.id)
                )).scalars().all()
                session.add_all([
                    NatInventory(company_id=seller.id, item_id=item_id, quantity=total_qty, avg_cost_basis=2.0)
                    for seller in sellers
                ])
                await session.flush()
                first_cash = sellers[0].cash

                first = await CityOrderService.deliver(
                    session, sellers[0].id, order["id"], partial_qty,
                    idempotency_key="city-test-delivery-1", now=start + timedelta(minutes=5),
                )
                after_first_cash = sellers[0].cash
                replay = await CityOrderService.deliver(
                    session, sellers[0].id, order["id"], partial_qty,
                    idempotency_key="city-test-delivery-1", now=start + timedelta(minutes=6),
                )
                assert first["cash_amount"] > 0
                assert replay["replayed"] is True
                assert sellers[0].cash == after_first_cash
                assert after_first_cash > first_cash

                remaining = round(order["quantity"] - partial_qty, 6)
                final = await CityOrderService.deliver(
                    session, sellers[1].id, order["id"], remaining,
                    idempotency_key="city-test-delivery-2", now=start + timedelta(minutes=10),
                )
                assert final["order_status"] == "FULFILLED"
                assert final["remaining_quantity"] == 0
                assert first["cash_amount"] + final["cash_amount"] == pytest.approx(order["reserved_cash"])
                assert await session.scalar(select(NatMarketTrade.id).limit(1)) is None
                ledger_rows = (await session.execute(select(NatCompanyProfitPeriod).where(
                    NatCompanyProfitPeriod.company_id == sellers[0].id
                ))).scalars().all()
                assert sum(row.realized_revenue for row in ledger_rows) == first["cash_amount"]
                assert sum(row.cost_of_goods_sold for row in ledger_rows) == pytest.approx(partial_qty * 2.0)

                with pytest.raises(ValueError):
                    await CityOrderService.deliver(
                        session, sellers[0].id, order["id"], 0.000001,
                        idempotency_key="city-test-delivery-overfill", now=start + timedelta(minutes=11),
                    )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_expiry_returns_only_remaining_escrow_and_delivery_after_deadline_is_rejected() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        start = datetime(2026, 9, 26, 12, 0)
        try:
            async with sessions() as session:
                issued = await CityOrderService.issue_due(session, now=start)
                order = issued["order"]
                seller = await session.get(NatCompany, company_ids[0])
                session.add(NatInventory(
                    company_id=seller.id, item_id=order["item_id"],
                    quantity=order["quantity"], avg_cost_basis=3.0,
                ))
                await session.flush()
                partial = round(order["quantity"] / 2, 6)
                await CityOrderService.deliver(
                    session, seller.id, order["id"], partial,
                    idempotency_key="city-expiry-partial", now=start + timedelta(minutes=15),
                )
                before_refund = (await session.get(NatStateTreasury, 1)).cash
                result = await CityOrderService.deliver(
                    session, seller.id, order["id"], 0.000001,
                    idempotency_key="city-after-expiry", now=start + timedelta(hours=1),
                )
                assert result["success"] is False and result["reason"] == "order_expired"
                await session.commit()
                after_refund = (await session.get(NatStateTreasury, 1)).cash
                updated = await CityOrderService.get_order(session, order["id"])
                assert updated["status"] == "EXPIRED"
                assert updated["reserved_cash"] == 0
                assert after_refund > before_refund
                released = await CityOrderService.expire_due(
                    session, now=start + timedelta(hours=2)
                )
                assert released == 0
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_company_reset_preserves_shared_order_and_anonymizes_delivery_ledger() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        start = datetime(2026, 9, 26, 12, 0)
        try:
            async with sessions() as session:
                issue = await CityOrderService.issue_due(session, now=start)
                order = issue["order"]
                company = await session.get(NatCompany, company_ids[0])
                session.add(NatInventory(
                    company_id=company.id, item_id=order["item_id"],
                    quantity=order["quantity"], avg_cost_basis=1.0,
                ))
                await session.flush()
                await CityOrderService.deliver(
                    session, company.id, order["id"], order["quantity"] / 2,
                    idempotency_key="city-reset-ledger", now=start + timedelta(minutes=2),
                )
                from backend.natbirzha.services.company_service import CompanyService
                await CompanyService.reset_company_for_user(session, company.user_id, commit=False)
                remaining_order = await CityOrderService.get_order(session, order["id"])
                delivery = await CityOrderService.get_delivery_by_key(session, "city-reset-ledger")
                assert remaining_order["status"] == "OPEN"
                assert delivery.company_id is None
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_world_reset_registry_includes_orders_cycle_and_delivery_ledger() -> None:
    from backend.natbirzha.services.world_reset_service import WorldResetService

    names = {table.name for table in WorldResetService.resettable_tables()}
    assert {
        "nat_city_orders", "nat_city_order_cycle_states", "nat_city_order_deliveries",
    } <= names
