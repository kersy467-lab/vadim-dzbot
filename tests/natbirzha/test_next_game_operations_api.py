import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base, User
import backend.natbirzha.models
import backend.natbirzha.models.next_game_operations
from backend.db.session import get_db_session
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.api.next_game_operations_routes import router


def test_authorization_idempotency_key_conflict_and_single_paid_expansion():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            await Game.create_company(session, 981003, "Компания API")
            company = await Game._owned_company(session, 981003)
            treasury = await Game._treasury(session)
            company.cash += 100000
            treasury.cash -= 100000
            for item in ("steel", "concrete"):
                await Game._change_inventory(session, company.id, item, 100)
            await session.commit()
        actor = {"role": "student"}
        async def user():
            return User(id=981003, tg_id=981003, full_name="Operations", role=actor["role"])
        async def db():
            async with sessions() as session:
                yield session
        app = FastAPI()
        app.include_router(router, prefix="/api/natbirzha")
        app.dependency_overrides[get_strict_natbirzha_user] = user
        app.dependency_overrides[get_db_session] = db
        try:
            with TestClient(app) as client:
                url = "/api/natbirzha/next-game/operations"
                assert client.get(url).status_code == 403
                assert client.post(url + "/actions", json={"action": "WAREHOUSE"},
                    headers={"Idempotency-Key": "unauthorized"}).status_code == 403
                actor["role"] = "admin"
                assert client.post(url + "/actions", json={"action": "WAREHOUSE"}).status_code == 400
                headers = {"Idempotency-Key": "warehouse-once"}
                first = client.post(url + "/actions", json={"action": "WAREHOUSE"}, headers=headers)
                replay = client.post(url + "/actions", json={"action": "WAREHOUSE"}, headers=headers)
                assert first.status_code == replay.status_code == 200
                assert first.json() == replay.json()
                assert client.post(url + "/actions", json={"action": "LAND"}, headers=headers).status_code == 409
                data = client.get(url).json()
                assert data["cash"] == 90000
                assert data["capacity"]["warehouse_level"] == 1
                assert data["capacity"]["warehouse_capacity"] == 150000
                assert client.post(url + "/actions", json={"action": "AUTOMATION", "facility_id": -1},
                    headers={"Idempotency-Key": "invalid-id"}).status_code == 422
        finally:
            await engine.dispose()
    asyncio.run(check())
