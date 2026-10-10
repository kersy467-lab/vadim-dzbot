import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api.next_game_routes import router as game_router
from backend.natbirzha.api.next_game_bond_routes import router as bond_router
from backend.natbirzha.api.next_game_market_routes import router as browser_router
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.config import nat_settings
from backend.natbirzha.next_game_catalog import get_next_game_items


def test_bond_and_browser_admin_auth_idempotency_and_actual_portfolio():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        actor = {"id": 96901}
        previous = nat_settings.CREATOR_TG_IDS
        nat_settings.CREATOR_TG_IDS = "96901"
        async def db():
            async with sessions() as session:
                yield session
        async def user():
            return User(id=1, tg_id=actor["id"], username="bonds", full_name="Bonds", role="student")
        app = FastAPI()
        for router in (game_router, bond_router, browser_router):
            app.include_router(router, prefix="/api/natbirzha")
        app.dependency_overrides[get_db_session] = db
        app.dependency_overrides[get_strict_natbirzha_user] = user
        base = "/api/natbirzha/next-game"
        try:
            with TestClient(app) as client:
                actor["id"] = 96902
                assert client.get(f"{base}/bonds").status_code == 403
                assert client.get(f"{base}/market/catalog").status_code == 403
                actor["id"] = 96901
                assert client.post(f"{base}/company", json={"name": "Инвестор API"}).status_code == 200
                catalog = client.get(f"{base}/market/catalog").json()
                assert {row["id"] for row in catalog["items"]} == set(get_next_game_items())
                item = client.get(f"{base}/market/items/energy").json()
                assert item["history"] == [] and item["reference_price"] is None
                assert client.get(f"{base}/market/liquidity").json()["items"] == []
                body = {"series_id": 1, "units": 10}
                assert client.post(f"{base}/bonds/buy", json=body).status_code == 400
                headers = {"Idempotency-Key": "bond-primary-1"}
                first = client.post(f"{base}/bonds/buy", json=body, headers=headers)
                replay = client.post(f"{base}/bonds/buy", json=body, headers=headers)
                assert first.status_code == replay.status_code == 200
                assert first.json() == replay.json()
                conflict = client.post(f"{base}/bonds/buy", json={**body, "units": 11}, headers=headers)
                assert conflict.status_code == 409
                listing = client.post(f"{base}/bonds/listings", json={
                    "holding_id": first.json()["holding_id"], "units": 4, "unit_price": 105,
                }, headers={"Idempotency-Key": "bond-list-1"})
                assert listing.status_code == 200
                portfolio = client.get(f"{base}/bonds").json()
                assert len(portfolio["series"]) == 3
                assert len(portfolio["holdings"]) == 1
                assert portfolio["holdings"][0]["free_units"] == 6
                listing_id = listing.json()["listing_id"]
                cancel_headers = {"Idempotency-Key": "bond-cancel-1"}
                cancelled = client.delete(f"{base}/bonds/listings/{listing_id}", headers=cancel_headers)
                replay_cancel = client.delete(f"{base}/bonds/listings/{listing_id}", headers=cancel_headers)
                assert cancelled.status_code == replay_cancel.status_code == 200
                assert cancelled.json() == replay_cancel.json()
                assert client.get(f"{base}/bonds").json()["holdings"][0]["free_units"] == 10
        finally:
            nat_settings.CREATOR_TG_IDS = previous
            await engine.dispose()
    asyncio.run(check())
