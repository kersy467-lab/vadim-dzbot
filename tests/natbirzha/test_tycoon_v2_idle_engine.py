"""Lazy settlement rules for career NATBIRZHA 2.0 businesses."""

import asyncio
from collections import Counter
from datetime import datetime, timedelta
from math import isclose
import re

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now
from backend.natbirzha.api.business_routes import empire_summary
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


async def create_mining_business(session, *, cash: float = 100_000.0, last_settled_at: datetime) -> tuple[NatCompany, NatBusiness]:
    spec = get_business_spec("coal_open_pit")
    company = NatCompany(user_id=8_001, name="Idle Corp", specialization="miner", cash=cash)
    session.add(company)
    await session.flush()
    # Seed every live recipe and recurring service input so this test exercises
    # settlement clocks rather than market availability.
    session.add_all([
        NatInventory(
            company_id=company.id,
            item_id=item_id,
            quantity=max(100.0, float(quantity) * 100),
            avg_cost_basis=CANONICAL_ITEMS[item_id]["base_price"],
        )
        for item_id, quantity in spec["inputs_per_hour"].items()
    ])
    business = NatBusiness(
        company_id=company.id,
        business_type=spec["id"],
        specialization="miner",
        stage=1,
        status="ACTIVE",
        capital_invested=spec["open_cost"],
        base_income_per_hour=spec["base_income_per_hour"],
        base_maintenance_per_hour=spec["base_maintenance_per_hour"],
        health=100.0,
        efficiency=1.0,
        metadata_json={"sale_mode": "NPC"},
        last_settled_at=last_settled_at,
    )
    session.add(business)
    await session.commit()
    return company, business


def expected_net_cash_per_hour(business: NatBusiness, *, upgrading: bool) -> float:
    spec = get_business_spec(business.business_type)
    rates = resource_business_rates(business, spec, upgrading=upgrading)
    # Resource outputs are always held in inventory; only maintenance moves
    # cash during offline production.
    return -rates.maintenance_per_hour


def test_idle_settlement_applies_once_and_stops_at_tax_period_close() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_mining_business(session, last_settled_at=start)
            hourly = expected_net_cash_per_hour(business, upgrading=False)
            first = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert first["net_cash"] == round(hourly, 2)
            assert first["xp_gained"] == 20
            assert first["progression"]["xp"] == 20
            assert first["progression"]["xp_to_next"] == 130
            assert company.cash == round(100_000.0 + hourly, 2)
            assert company.xp == 20
            coal = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company.id, NatInventory.item_id == "coal"
            ))
            assert coal is not None and coal.quantity > 0
            assert business.last_settled_at == start + timedelta(hours=1)

            repeated = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert repeated["net_cash"] == 0.0

            # Tax blocking applies when the company has realized profit. This
            # miner's HOLD output alone is inventory, not taxable revenue.
            await CompanyProfitLedgerService.record_period(
                session,
                company.id,
                start,
                start + timedelta(hours=12),
                revenue=1_000.0,
            )

            # Unpaid tax blocks production at the close of its 12-hour period,
            # even when the requested offline window is longer.
            capped = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=50))
            assert capped["settled_hours"] == 11.0
            assert capped["tax_blocked"] is True
            assert business.last_settled_at == start + timedelta(hours=50)

            blocked_repeat = await IdleEconomyService.settle_company(
                session, company.id, now=start + timedelta(hours=50)
            )
            assert blocked_repeat["settled_hours"] == 0.0
            assert blocked_repeat["net_cash"] == 0.0

        await engine.dispose()

    asyncio.run(check())


def test_idle_settlement_completes_upgrade_mid_window() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_mining_business(session, last_settled_at=start)
            business.status = "UPGRADING"
            business.upgrade_target_stage = 2
            business.upgrade_started_at = start
            business.upgrade_ready_at = start + timedelta(minutes=30)
            before = expected_net_cash_per_hour(business, upgrading=True)
            await session.commit()

            # Compute stage-2 active rate on a detached-like copy of the same row.
            business.stage = 2
            business.status = "ACTIVE"
            after = expected_net_cash_per_hour(business, upgrading=False)
            business.stage = 1
            business.status = "UPGRADING"
            await session.flush()

            settlement = await IdleEconomyService.settle_company(session, company.id, now=start + timedelta(hours=1))
            assert settlement["net_cash"] == round((before + after) / 2, 2)
            assert settlement["xp_gained"] == 90  # one productive hour + stage-2 completion reward
            assert settlement["progression"]["xp"] == 90
            assert business.stage == 2
            assert business.status == "ACTIVE"
            assert business.upgrade_ready_at is None

        await engine.dispose()

    asyncio.run(check())


def test_idle_settlement_never_moves_a_business_clock_backwards() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 9, 20, 12, 0)

        async with sessions() as session:
            company, business = await create_mining_business(session, last_settled_at=start)
            settlement = await IdleEconomyService.settle_company(session, company.id, now=start - timedelta(minutes=5))
            assert settlement["settled_hours"] == 0.0
            assert company.cash == 100_000.0
            assert business.last_settled_at == start

        await engine.dispose()

    asyncio.run(check())


def test_idle_settlement_batches_contract_license_checks() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = get_game_now()
            company = NatCompany(
                user_id=8_009,
                name="License Batch Corp",
                specialization="miner",
                cash=100_000,
            )
            session.add(company)
            await session.flush()
            businesses = [
                NatBusiness(
                    company_id=company.id,
                    business_type="coal_open_pit",
                    specialization="miner",
                    stage=1,
                    status="ACTIVE",
                    last_settled_at=now - timedelta(hours=1),
                    metadata_json={"contract_license": "missing-test-license"},
                )
                for _ in range(24)
            ]
            session.add_all(businesses)
            await session.flush()

            license_queries = []

            def capture_license_query(_conn, _cursor, statement, *_args):
                if "from nat_premium_licenses" in statement.lower():
                    license_queries.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", capture_license_query)
            try:
                await IdleEconomyService.settle_company(session, company.id, now=now)
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", capture_license_query)

            assert len(license_queries) <= 1, (
                "contract license checks should use one batch query per company; "
                f"got {len(license_queries)} for {len(businesses)} leased businesses"
            )
            assert all(business.status == "PAUSED_MANUAL" for business in businesses)
            assert all(business.metadata_json["contract_expired"] for business in businesses)

        await engine.dispose()

    asyncio.run(check())


def test_empire_summary_bounds_cold_and_warm_resource_settlement_queries() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            now = get_game_now()
            company = NatCompany(
                user_id=8_010,
                name="Settlement Query Budget Corp",
                specialization="miner",
                level=40,
                cash=1_000_000,
            )
            session.add(company)
            await session.flush()
            spec = get_business_spec("coal_open_pit")
            item_ids = set(spec["inputs_per_hour"]) | set(spec["outputs_per_hour"])
            session.add_all([
                NatInventory(
                    company_id=company.id,
                    item_id=item_id,
                    quantity=1_000_000.0 if item_id in spec["inputs_per_hour"] else 0.0,
                    reserved_quantity=0.0,
                    avg_cost_basis=1.0,
                )
                for item_id in item_ids
            ])
            businesses = [
                NatBusiness(
                    company_id=company.id,
                    business_type=spec["id"],
                    specialization="miner",
                    stage=1,
                    status="ACTIVE",
                    last_settled_at=now - timedelta(hours=24),
                    metadata_json={},
                )
                for _ in range(30)
            ]
            session.add_all(businesses)
            await session.flush()

            for label in ("cold", "warm"):
                statements = []

                def capture_statement(_conn, _cursor, statement, *_args):
                    statements.append(statement.lower())

                event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
                try:
                    summary = await empire_summary(company, session)
                finally:
                    event.remove(engine.sync_engine, "before_cursor_execute", capture_statement)

                select_statements = [sql for sql in statements if sql.lstrip().startswith("select")]
                inventory_reads = sum("from nat_inventory" in sql for sql in select_statements)
                policy_reads = sum("from nat_business_supply_policies" in sql for sql in select_statements)
                deal_reads = sum("from nat_supply_deals" in sql for sql in select_statements)
                daily_reads = sum("from nat_business_income_daily" in sql for sql in select_statements)
                business_period_reads = sum("from nat_business_income_periods" in sql for sql in select_statements)
                table_reads = Counter(
                    table
                    for sql in select_statements
                    for table in re.findall(r"\bfrom\s+([a-z_][a-z0-9_]*)", sql)
                )
                operation_counts = Counter()
                for sql in statements:
                    operation_match = re.match(r"\s*(select|insert|update|delete)\b", sql)
                    if operation_match:
                        operation_counts[operation_match.group(1)] += 1
                assert (
                    inventory_reads <= 2
                    and policy_reads <= 2
                    and daily_reads <= 1
                    and business_period_reads <= 1
                    and deal_reads <= 6
                    and len(statements) <= 230
                ), (
                    f"{label} settlement query budget exceeded for 30 resource businesses: "
                    f"total={len(statements)}, inventory={inventory_reads}, "
                    f"policies={policy_reads}, daily={daily_reads}, "
                    f"business_periods={business_period_reads}, deals={deal_reads}, "
                    f"tables={dict(table_reads)}"
                )
                print(
                    f"{label} query profile: total={len(statements)}, "
                    f"inventory={inventory_reads}, policies={policy_reads}, "
                    f"daily={daily_reads}, business_periods={business_period_reads}, "
                    f"deals={deal_reads}, operations={dict(operation_counts)}, "
                    f"tables={dict(table_reads)}"
                )
                if label == "cold":
                    settlement = summary["settlement"]
                    rates = resource_business_rates(businesses[0], spec, upgrading=False)
                    outputs = {
                        row.item_id: float(row.quantity)
                        for row in (await session.execute(
                            select(NatInventory).where(
                                NatInventory.company_id == company.id,
                                NatInventory.item_id.in_(spec["outputs_per_hour"]),
                            )
                        )).scalars().all()
                    }
                    expected_value = round(sum(
                        outputs.get(item_id, 0.0) * CANONICAL_ITEMS[item_id]["base_price"]
                        for item_id in spec["outputs_per_hour"]
                    ), 2)
                    output_hours = [
                        outputs.get(item_id, 0.0)
                        / (float(quantity) * rates.output_multiplier * len(businesses))
                        for item_id, quantity in spec["outputs_per_hour"].items()
                    ]
                    expected_maintenance = round(
                        rates.maintenance_per_hour * output_hours[0] * len(businesses), 2
                    )
                    assert 0 < settlement["settled_hours"] <= 24
                    assert settlement["gross_cash"] == 0.0
                    assert isclose(settlement["gross_value"], expected_value, abs_tol=0.02)
                    assert settlement["maintenance_cash"] == expected_maintenance
                    assert settlement["net_cash"] == round(-expected_maintenance, 2)

        await engine.dispose()

    asyncio.run(check())
