"""Shared V2 resource-stock runway in the existing empire-summary response."""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import Depends, Header
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
from backend.db.session import get_db_session
from backend.main import app
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.auth_service import get_current_company


def _business(company_id: int, business_type: str, *, stage: int = 1, status: str = "ACTIVE") -> NatBusiness:
    return NatBusiness(
        company_id=company_id,
        business_type=business_type,
        specialization="miner",
        stage=stage,
        status=status,
        base_income_per_hour=0.0,
        base_maintenance_per_hour=0.0,
        health=100.0,
        efficiency=1.0,
        last_settled_at=datetime(2099, 1, 1),
    )


def test_empire_summary_reports_aggregate_v2_inventory_runway() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            users = [
                User(tg_id=-984001 - index, full_name=f"Runway Owner {index}", role="guest", is_tester=False)
                for index in range(3)
            ]
            session.add_all(users)
            await session.flush()
            companies = [
                NatCompany(user_id=user.id, name=f"Runway Company {index}", specialization="miner", cash=30_000)
                for index, user in enumerate(users)
            ]
            session.add_all(companies)
            await session.flush()
            session.add_all([
                _business(companies[0].id, "coal_open_pit", stage=1),
                _business(companies[0].id, "coal_open_pit", stage=2, status="UPGRADING"),
                _business(companies[0].id, "coal_open_pit", stage=40, status="PAUSED_MANUAL"),
                _business(companies[0].id, "coal_open_pit", stage=1, status="PAUSED_SUPPLY"),
                _business(companies[0].id, "coal_open_pit", stage=40, status="PAUSED_STORAGE"),
                _business(companies[0].id, "coal_open_pit", stage=40, status="PAUSED_MAINTENANCE"),
                _business(companies[0].id, "coal_open_pit", stage=40, status="BANKRUPT"),
                _business(companies[0].id, "coal_open_pit", stage=40, status="MERGING"),
                _business(companies[0].id, "mining_company", stage=40, status="ACTIVE"),
                _business(companies[1].id, "coal_open_pit"),
            ])
            session.add_all([
                NatInventory(company_id=companies[0].id, item_id="energy", quantity=426.1582872, reserved_quantity=42.6309672),
                NatInventory(company_id=companies[0].id, item_id="water", quantity=1_000_000, reserved_quantity=0),
                NatInventory(company_id=companies[0].id, item_id="fuel_diesel", quantity=1_000_000, reserved_quantity=0),
                NatInventory(company_id=companies[0].id, item_id="food", quantity=1_000_000, reserved_quantity=0),
                NatInventory(company_id=companies[0].id, item_id="ai_compute", quantity=1_000_000, reserved_quantity=0),
                NatInventory(company_id=companies[0].id, item_id="beer", quantity=1_000_000, reserved_quantity=0),
            ])
            await session.commit()

        async def override_db():
            async with sessions() as session:
                yield session

        async def override_company(
            x_telegram_user_id: str = Header(..., alias="X-Telegram-User-Id"),
            session=Depends(get_db_session),
        ):
            user = await session.scalar(select(User).where(User.tg_id == int(x_telegram_user_id)))
            return await session.scalar(select(NatCompany).where(NatCompany.user_id == user.id))

        app.dependency_overrides[get_db_session] = override_db
        app.dependency_overrides[get_current_company] = override_company
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                stocked = await client.get(
                    "/api/natbirzha/company/empire-summary",
                    headers={"X-Telegram-User-Id": "-984001"},
                )
                assert stocked.status_code == 200, stocked.text
                payload = stocked.json()
                runway = payload["inventory_runway"]
                assert runway["status"] == "RUNWAY"
                assert runway["hours"] == 2.0
                assert runway["active_consuming_business_count"] == 3
                assert runway["consumption_per_hour"]["energy"] == 191.76366
                assert [item["item_id"] for item in runway["limiting_resources"]] == ["energy"]
                assert runway["limiting_resources"][0]["available_quantity"] == 383.52732
                assert payload["inventory_available"]["energy"] == 383.52732

                dry = await client.get(
                    "/api/natbirzha/company/empire-summary",
                    headers={"X-Telegram-User-Id": "-984002"},
                )
                assert dry.status_code == 200, dry.text
                dry_runway = dry.json()["inventory_runway"]
                assert dry_runway["status"] == "OUT_OF_STOCK"
                assert dry_runway["hours"] == 0.0
                assert dry_runway["active_consuming_business_count"] == 1
                assert "energy" in {item["item_id"] for item in dry_runway["limiting_resources"]}

                idle = await client.get(
                    "/api/natbirzha/company/empire-summary",
                    headers={"X-Telegram-User-Id": "-984003"},
                )
                assert idle.status_code == 200, idle.text
                idle_runway = idle.json()["inventory_runway"]
                assert idle_runway["status"] == "NO_CONSUMERS"
                assert idle_runway["hours"] is None
                assert idle_runway["active_consuming_business_count"] == 0
                assert idle_runway["limiting_resources"] == []
        finally:
            app.dependency_overrides.pop(get_db_session, None)
            app.dependency_overrides.pop(get_current_company, None)
            await engine.dispose()

    asyncio.run(run())
