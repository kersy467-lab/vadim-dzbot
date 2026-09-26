"""The temporary launch gate must protect APIs, not only hide the frontend."""

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import build_natbirzha_router
from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user


def test_admin_only_mode_keeps_login_open_and_blocks_game_apis_for_players():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        previous_mode = nat_settings.ADMIN_ONLY_ACCESS
        previous_creators = nat_settings.CREATOR_TG_IDS
        nat_settings.ADMIN_ONLY_ACCESS = True
        nat_settings.CREATOR_TG_IDS = "990001"
        actor = {"user": User(id=1, tg_id=990002, username="player", full_name="Player", role="student")}

        async def db_session():
            async with sessions() as session:
                yield session

        async def current_user():
            return actor["user"]

        app = FastAPI()
        app.include_router(build_natbirzha_router(admin_only=True), prefix="/api")
        app.dependency_overrides[get_db_session] = db_session
        app.dependency_overrides[get_strict_natbirzha_user] = current_user
        try:
            with TestClient(app) as client:
                login = client.post("/api/natbirzha/auth/login")
                assert login.status_code == 200
                assert login.json()["game_access"] is False
                assert "has_company" not in login.json()

                blocked = client.get("/api/natbirzha/company/industries")
                assert blocked.status_code == 403
                assert blocked.json()["detail"]["code"] == "GAME_ACCESS_CLOSED"

                actor["user"] = User(
                    id=2, tg_id=990003, username="fake-admin", full_name="Fake Admin", role="admin"
                )
                forged_role = client.get("/api/natbirzha/company/industries")
                assert forged_role.status_code == 403

                actor["user"] = User(
                    id=3, tg_id=990001, username="owner", full_name="Admin", role="admin"
                )
                admin_login = client.post("/api/natbirzha/auth/login")
                assert admin_login.status_code == 200
                assert admin_login.json()["game_access"] is True
                allowed = client.get("/api/natbirzha/company/industries")
                assert allowed.status_code == 200
        finally:
            nat_settings.ADMIN_ONLY_ACCESS = previous_mode
            nat_settings.CREATOR_TG_IDS = previous_creators
            await engine.dispose()

    asyncio.run(check())
