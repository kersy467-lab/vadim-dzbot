"""Regression contracts for paused enterprises and the premium lithium lease."""

import asyncio
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.catalogs.businesses import BUSINESS_CATALOG, CAREER_BUSINESSES, INDUSTRIES
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.premium import NatPremiumLicense
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.stock_service import StockService


def test_ai_data_centers_replace_forestry_and_supply_industry_demand() -> None:
    ai_businesses = sorted(
        (spec for spec in CAREER_BUSINESSES.values()
         if spec["specialization"] == "ai_data" and not spec.get("hybrid_only") and not spec.get("rebirth_required")),
        key=lambda spec: spec["industry_order"],
    )
    assert "ai_data" in INDUSTRIES
    assert len(ai_businesses) == 9
    assert ai_businesses[0]["starter"] is True
    assert [spec["industry_order"] for spec in ai_businesses] == list(range(1, 10))
    assert all(spec["open_resources"] for spec in ai_businesses[1:])
    by_id = {spec["id"]: spec for spec in ai_businesses}
    assert by_id["ai_compute_node"]["outputs_per_hour"].get("ai_compute", 0) > 0
    assert all("ai_compute" not in spec["inputs_per_hour"] for spec in ai_businesses)
    assert "forest_management_v2" not in CAREER_BUSINESSES
    assert BUSINESS_CATALOG["forest_management_v2"]["legacy_hidden"] is True

    # Every other sector starts with a small AI-service input, dips at midgame,
    # and pays more again as later production tiers automate.
    assert CAREER_BUSINESSES["grain_farm_v2"]["resource_network_inputs"]["ai_compute"] == 1.15
    assert CAREER_BUSINESSES["lubricant_factory_v2"]["resource_network_inputs"]["ai_compute"] < 1.0
    assert CAREER_BUSINESSES["agro_holding_v2"]["resource_network_inputs"]["ai_compute"] > 1.0


def test_paused_idle_enterprise_upgrade_is_available_and_keeps_its_pause_reason() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=991_221, name="Paused AI", specialization="ai_data",
                level=20, cash=1_000_000, territory_tiles=20,
            )
            session.add(company)
            await session.flush()
            business = NatBusiness(
                company_id=company.id, business_type="ai_compute_node",
                specialization="ai_data", stage=1, status="PAUSED_SUPPLY",
                last_settled_at=get_game_now().replace(tzinfo=None),
            )
            session.add(business)
            await session.commit()
            company_id, business_id = company.id, business.id

        app = FastAPI()
        app.include_router(natbirzha_router, prefix="/api")

        async def test_session():
            async with sessions() as session:
                yield session

        async def test_company(session: AsyncSession = Depends(get_db_session)):
            return await session.get(NatCompany, company_id)

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_current_company] = test_company
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=True),
            base_url="http://test",
            headers={"X-Natbirzha-Guest-Id": "paused-ai-upgrade-test-guest"},
        ) as client:
            portfolio = await client.get("/api/natbirzha/businesses")
            assert portfolio.status_code == 200, portfolio.text
            assert portfolio.json()["businesses"][0]["next_upgrade"] is not None
            response = await client.post(
                f"/api/natbirzha/businesses/{business_id}/upgrade",
                headers={"Idempotency-Key": "paused-business-upgrade"},
            )

        assert response.status_code == 200, response.text
        assert isinstance(response.json()["ready_at"], str)
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=True),
            base_url="http://test",
            headers={"X-Natbirzha-Guest-Id": "paused-ai-upgrade-test-guest"},
        ) as client:
            replay = await client.post(
                f"/api/natbirzha/businesses/{business_id}/upgrade",
                headers={"Idempotency-Key": "paused-business-upgrade"},
            )
        assert replay.status_code == 200 and replay.json() == response.json()
        async with sessions() as session:
            business = await session.get(NatBusiness, business_id)
            assert business.status == "UPGRADING"
            assert business.metadata_json["upgrade_resume_status"] == "PAUSED_SUPPLY"
            business.upgrade_ready_at = get_game_now() - timedelta(seconds=1)
            await session.flush()
            from backend.natbirzha.catalogs.businesses import get_business_spec
            from backend.natbirzha.services.idle_economy_service import IdleEconomyService

            IdleEconomyService._finish_due_upgrade(
                business, get_business_spec(business.business_type)
            )
            assert business.stage == 2
            assert business.status == "PAUSED_SUPPLY"
            assert "upgrade_resume_status" not in business.metadata_json

        await engine.dispose()

    asyncio.run(check())


def test_rare_mining_contract_grants_visible_business_and_preserves_upgrades() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(
                user_id=991_222, name="Lithium Contract", specialization="miner",
                level=60, cash=2_000_000, pvc_balance=500, territory_tiles=20,
            )
            session.add(company)
            await session.flush()
            session.add(NatFactory(
                company_id=company.id, building_type="iron_mine", specialization="miner",
                level=1, workers=30, is_active=True,
            ))
            await session.commit()
            company_id = company.id

        app = FastAPI()
        app.include_router(natbirzha_router, prefix="/api")

        async def test_session():
            async with sessions() as session:
                yield session

        async def test_company(session: AsyncSession = Depends(get_db_session)):
            return await session.get(NatCompany, company_id)

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_current_company] = test_company
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={"X-Natbirzha-Guest-Id": "rare-mining-contract-test-guest"},
        ) as client:
            first = await client.post(
                "/api/natbirzha/premium/licenses/rare_mining/purchase",
                headers={"Idempotency-Key": "lithium-contract-first"},
            )
            assert first.status_code == 200, first.text
            assert first.json()["license"]["expires_at"]
            assert first.json()["contract"]["business_granted"] is True
            assert first.json()["contract"]["price_cash"] == 0
            upgraded = await client.post(
                f"/api/natbirzha/businesses/{first.json()['contract']['business_id']}/upgrade",
                headers={"Idempotency-Key": "lithium-contract-upgrade"},
            )
            assert upgraded.status_code == 200, upgraded.text
            assert upgraded.json()["target_stage"] == 2

            async with sessions() as session:
                business = await session.scalar(select(NatBusiness).where(
                    NatBusiness.company_id == company_id,
                    NatBusiness.business_type == "lithium_quarry_v2",
                ))
                assert business is not None
                business_id = business.id
                assert business.stage == 1 and business.status == "UPGRADING"
                business.upgrade_ready_at = get_game_now() - timedelta(seconds=1)
                license_row = await session.scalar(select(NatPremiumLicense).where(
                    NatPremiumLicense.company_id == company_id,
                    NatPremiumLicense.license_code == "rare_mining",
                ))
                assert license_row.expires_at - license_row.starts_at == timedelta(hours=72)
                license_row.expires_at = datetime.utcnow() - timedelta(seconds=1)
                await session.commit()

            portfolio = await client.get("/api/natbirzha/businesses")
            assert portfolio.status_code == 200, portfolio.text
            leased = next(row for row in portfolio.json()["businesses"] if row["id"] == business_id)
            assert leased["contract_expired"] is True
            assert leased["next_upgrade"] is None
            locked_upgrade = await client.post(
                f"/api/natbirzha/businesses/{business_id}/upgrade",
                headers={"Idempotency-Key": "lithium-contract-upgrade-expired"},
            )
            assert locked_upgrade.status_code == 400

            renewed = await client.post(
                "/api/natbirzha/premium/licenses/rare_mining/purchase",
                headers={"Idempotency-Key": "lithium-contract-renew"},
            )
            assert renewed.status_code == 200, renewed.text
            assert renewed.json()["contract"]["stage"] == 2

        async with sessions() as session:
            businesses = (await session.execute(select(NatBusiness).where(
                NatBusiness.company_id == company_id,
                NatBusiness.business_type == "lithium_quarry_v2",
            ))).scalars().all()
            assert len(businesses) == 1
            assert businesses[0].stage == 2
            assert businesses[0].status == "PAUSED_SUPPLY"
            assert businesses[0].metadata_json.get("contract_expired") is None

        await engine.dispose()

    asyncio.run(check())


def test_ipo_can_commit_all_profit_and_pays_only_shares_actually_held() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            company = NatCompany(
                user_id=991_223, name="Full Dividend IPO", specialization="ai_data",
                level=60, cash=100_000, territory_tiles=20,
            )
            session.add(company)
            await session.flush()
            stock = await StockService.apply_for_ipo(
                session, company, dividend_rate_pct=100.0
            )
            day = get_game_now().date()
            session.add(NatDailyFinancials(
                company_id=company.id, calendar_date=day, gross_revenue=1_000,
                opex=0, closed_profit=1_000, developer_fee_paid=0, created_at=get_game_now(),
            ))
            await session.commit()
            result = await DividendService.settle_daily_dividends_for_stock(
                session, stock, settlement_date=day
            )
            assert stock.dividend_rate_pct == 100.0
            assert result["dividend_pool"] == 600.0
            assert result["per_share"] == 0.1
        await engine.dispose()

    asyncio.run(check())
