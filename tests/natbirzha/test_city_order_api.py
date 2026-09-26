"""Route authentication and HTTP idempotency for city order deliveries."""

import asyncio
from datetime import timedelta

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
from backend.db.session import get_db_session
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api.city_order_routes import router
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.city_order_service import CityOrderService


def test_delivery_route_authentication_and_idempotent_retry() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            user = User(tg_id=991499, full_name="City Supplier")
            session.add(user)
            await session.flush()
            company = NatCompany(
                user_id=user.id, name="City Supplier Co", specialization="miner", cash=1000,
            )
            session.add_all([company, NatStateTreasury(id=1, cash=100_000)])
            await session.flush()
            issued = await CityOrderService.issue_due(session, now=get_game_now())
            order = issued["order"]
            session.add(NatInventory(
                company_id=company.id, item_id=order["item_id"],
                quantity=order["quantity"], avg_cost_basis=2.0,
            ))
            await session.commit()

            async def override_session():
                yield session

            async def override_company():
                return company

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db_session] = override_session
            app.dependency_overrides[get_current_company] = override_company
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                ) as client:
                    listed = await client.get("/market/city-orders")
                    assert listed.status_code == 200
                    assert listed.json()["orders"][0]["id"] == order["id"]
                    original_cash = company.cash
                    body = {"quantity": order["quantity"] / 2}
                    headers = {"Idempotency-Key": "city-route-retry-1"}
                    first = await client.post(
                        f"/market/city-orders/{order['id']}/deliver", json=body, headers=headers,
                    )
                    retry = await client.post(
                        f"/market/city-orders/{order['id']}/deliver", json=body, headers=headers,
                    )
                    assert first.status_code == retry.status_code == 200
                    assert first.json() == retry.json()
                    assert company.cash > original_cash
                    after = company.cash
                    conflict = await client.post(
                        f"/market/city-orders/{order['id']}/deliver",
                        json={"quantity": order["quantity"] / 3}, headers=headers,
                    )
                    assert conflict.status_code == 409
                    assert company.cash == after
            finally:
                app.dependency_overrides.clear()
        await engine.dispose()

    asyncio.run(check())
