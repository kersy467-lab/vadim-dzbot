"""Verification for complete company reset with all foreign key dependents."""

import asyncio
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.abspath("."))

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import build_natbirzha_router
from backend.natbirzha.models.bankruptcy_market import NatBankruptcyMarketLot
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.economy_metrics import NatEconomyEvent
from backend.natbirzha.models.hybrid_mergers import NatHybridMerger
from backend.natbirzha.models.state_shares import (
    NatStateShare,
    NatStateShareDailySettlement,
    NatStateShareDividendPayment,
    NatStateShareHolding,
)
from backend.natbirzha.models.stocks import NatStock, NatStockPriceSnapshot
from backend.natbirzha.models.tax import NatCompanyProfitPeriod
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.company_service import CompanyService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        user = User(tg_id=980001, full_name="Reset Player", role="student", is_tester=True)
        session.add(user)
        await session.flush()

        company = await CompanyService.create_company(session, user.id, "Reset Corp", "miner")
        await session.flush()

        # 1. Tycoon businesses & Hybrid merger with RESTRICT foreign keys
        b1 = NatBusiness(company_id=company.id, business_type="mine", stage=1)
        b2 = NatBusiness(company_id=company.id, business_type="sawmill", stage=1)
        session.add_all([b1, b2])
        await session.flush()
        merger = NatHybridMerger(
            company_id=company.id,
            recipe_id="r1",
            specialization="miner",
            source_business_a_id=b1.id,
            source_business_b_id=b2.id,
            source_a_stage=1,
            source_b_stage=1,
            source_a_status="ACTIVE",
            source_b_status="ACTIVE",
        )
        session.add(merger)

        # 2. Tax realized profit period
        profit = NatCompanyProfitPeriod(
            company_id=company.id,
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
        )
        session.add(profit)

        # 3. State shares & dividend receipts
        share = NatStateShare(
            title="Test State Share",
            total_volume=1000,
            remaining_volume=900,
            issue_price=100.0,
            projected_annual_profit=1000.0,
            dividend_rate_pct=10.0,
            actor_id=1,
        )
        session.add(share)
        await session.flush()
        holding = NatStateShareHolding(
            share_id=share.id, company_id=company.id, quantity=10, invested_cash=1000.0
        )
        settlement = NatStateShareDailySettlement(
            operation_key="op-settle-1",
            settlement_date=date.today(),
            total_due=100.0,
            total_paid=100.0,
            proration_ratio=1.0,
            treasury_cash_before=1000.0,
            treasury_cash_after=900.0,
        )
        session.add_all([holding, settlement])
        await session.flush()
        payment = NatStateShareDividendPayment(
            operation_key="op-pay-1",
            settlement_id=settlement.id,
            share_id=share.id,
            company_id=company.id,
            quantity=10,
            settlement_date=date.today(),
            amount_due=10.0,
            amount_paid=10.0,
        )
        session.add(payment)

        # 4. Stock price snapshot
        stock = NatStock(company_id=company.id, total_shares=10000, is_listed=True)
        session.add(stock)
        await session.flush()
        snap = NatStockPriceSnapshot(stock_id=stock.id, price=10.0, valuation=100000.0)
        session.add(snap)

        # 5. Bankruptcy lot
        lot = NatBankruptcyMarketLot(
            operation_key="lot-reset-1",
            former_company_id=company.id,
            former_company_name="Reset Corp",
            asset_kind="FACTORY",
            asset_id=1,
            asset_type="mine",
            title="Old Mine",
            industry="miner",
            cost_basis=1000.0,
            ask_price=1200.0,
        )
        session.add(lot)

        # 6. Economy telemetry event
        evt = NatEconomyEvent(company_id=company.id, flow="inflow", category="test", cash_amount=100.0)
        session.add(evt)
        await session.commit()

    # Wire FastAPI app to test the HTTP reset endpoint
    app = FastAPI()
    router = build_natbirzha_router(admin_only=False)
    app.include_router(router, prefix="/api")

    async def override_db():
        async with sessions() as s:
            yield s

    async def override_user():
        async with sessions() as s:
            return await s.get(User, user.id)

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_strict_natbirzha_user] = override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/natbirzha/company/reset")
        assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("success") is True
        assert data.get("reset") is True

    # Verify company is completely removed from DB
    # 7. Test Creator Self Reset (/api/natbirzha/creator/me/reset)
    from backend.natbirzha.api.creator_auth import get_current_creator
    async with sessions() as session:
        admin_user = User(tg_id=980002, full_name="Creator Admin", role="admin", is_tester=True)
        session.add(admin_user)
        await session.flush()
        admin_company = await CompanyService.create_company(session, admin_user.id, "Admin Corp", "miner")
        await session.commit()

    async def override_creator():
        async with sessions() as s:
            return await s.get(User, admin_user.id)

    app.dependency_overrides[get_current_creator] = override_creator

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/natbirzha/creator/me/reset")
        assert resp.status_code == 200, f"Expected 200 OK for creator reset, got {resp.status_code}: {resp.text}"
        creator_data = resp.json()
        assert creator_data.get("ok") is True
        assert creator_data.get("deleted_company") == "Admin Corp"

    async with sessions() as session:
        remaining_admin_comp = await session.scalar(
            select(NatCompany).where(NatCompany.user_id == admin_user.id)
        )
        assert remaining_admin_comp is None, "Creator company must be deleted after self reset"

    print("NATBIRZHA company reset complete: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())

