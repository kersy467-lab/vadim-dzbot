"""HTTP-level P0 verification without importing the Telegram bot runtime."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from backend.db.models import Base
from backend.db.session import async_session_factory, engine
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.config import get_game_now, nat_settings
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory


def signed_headers(tg_id: int, key: str | None = None) -> dict[str, str]:
    values = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": tg_id, "first_name": f"P0-{tg_id}"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    secret = hmac.new(b"WebAppData", nat_settings.TEST_AUTH_SECRET.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    headers = {"X-Telegram-Init-Data": urlencode(values)}
    if key:
        headers["Idempotency-Key"] = key
    return headers


async def reset_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def run() -> None:
    await reset_database()
    old_test_auth = nat_settings.ALLOW_TEST_AUTH
    old_creators = nat_settings.CREATOR_TG_IDS
    nat_settings.ALLOW_TEST_AUTH = True
    nat_settings.CREATOR_TG_IDS = "990001"

    app = FastAPI()
    app.include_router(natbirzha_router, prefix="/api")
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            user_id = 990002
            auth = signed_headers(user_id)

            unsigned = {"X-Telegram-Init-Data": urlencode({"user": json.dumps({"id": user_id})})}
            assert (await client.post("/api/natbirzha/auth/login", headers=unsigned)).status_code == 401
            login = await client.post("/api/natbirzha/auth/login", headers=auth)
            assert login.status_code == 200 and login.json()["user"]["is_creator"] is False

            guest_headers = {"X-Natbirzha-Guest-Id": "browser-guest-p0-2026"}
            guest_login = await client.post("/api/natbirzha/auth/login", headers=guest_headers)
            assert guest_login.status_code == 200
            assert guest_login.json()["user"]["tg_id"] < 0

            create_headers = {**auth, "Idempotency-Key": "company-create-1"}
            payload = {"name": "P0 API Corp", "specialization": "agrarian"}
            created = await client.post("/api/natbirzha/company/create", headers=create_headers, json=payload)
            replay_created = await client.post("/api/natbirzha/company/create", headers=create_headers, json=payload)
            assert created.status_code == 200 and replay_created.json() == created.json()
            assert created.json()["cash"] == 50000.0

            state = await client.get("/api/natbirzha/company/me", headers=auth)
            assert state.status_code == 200
            factory = state.json()["factories"][0]
            assert factory["current_recipe"] is None and factory["is_running"] is False
            assert factory["default_recipe"] == "farm_grain"
            factory_id = factory["id"]
            company_id = state.json()["id"]

            async with async_session_factory() as session:
                count = (await session.execute(select(func.count(NatCompany.id)))).scalar_one()
                assert count == 1

            start_headers = {**auth, "Idempotency-Key": "cycle-start-1"}
            started = await client.post(
                f"/api/natbirzha/production/factory/{factory_id}/start",
                headers=start_headers,
                params={"recipe_id": "farm_grain"},
            )
            replay_start = await client.post(
                f"/api/natbirzha/production/factory/{factory_id}/start",
                headers=start_headers,
                params={"recipe_id": "farm_grain"},
            )
            assert started.status_code == 200 and started.json()["status"] == "running"
            assert replay_start.json() == started.json()

            conflict = await client.post(
                f"/api/natbirzha/production/factory/{factory_id}/start",
                headers={**auth, "Idempotency-Key": "cycle-start-2"},
                params={"recipe_id": "farm_grain"},
            )
            assert conflict.status_code == 409

            async with async_session_factory() as session:
                fac = await session.get(NatFactory, factory_id)
                fac.cycle_ready_at = get_game_now() - timedelta(seconds=1)
                await session.commit()

            collect_headers = {**auth, "Idempotency-Key": "cycle-collect-1"}
            collected = await client.post(
                f"/api/natbirzha/production/factory/{factory_id}/collect",
                headers=collect_headers,
            )
            replay_collect = await client.post(
                f"/api/natbirzha/production/factory/{factory_id}/collect",
                headers=collect_headers,
            )
            assert collected.status_code == 200 and replay_collect.json() == collected.json()
            grain_out = collected.json()["outputs_produced"]["grain"]

            async with async_session_factory() as session:
                grain = (await session.execute(select(NatInventory).where(
                    NatInventory.company_id == company_id,
                    NatInventory.item_id == "grain",
                ))).scalar_one()
                assert grain.quantity == grain_out
                fac = await session.get(NatFactory, factory_id)
                assert fac.current_recipe is None and fac.cycle_ready_at is None

            # Same NPC mutation key must not charge or credit twice.
            cash_before = (await client.get("/api/natbirzha/company/me", headers=auth)).json()["cash"]
            npc_headers = {**auth, "Idempotency-Key": "npc-buy-1"}
            npc_payload = {"item_id": "water", "action": "BUY", "quantity": 2.0}
            npc_first = await client.post("/api/natbirzha/market/npc/trade", headers=npc_headers, json=npc_payload)
            npc_replay = await client.post("/api/natbirzha/market/npc/trade", headers=npc_headers, json=npc_payload)
            assert npc_first.status_code == 200 and npc_replay.json() == npc_first.json()
            cash_after = (await client.get("/api/natbirzha/company/me", headers=auth)).json()["cash"]
            assert round(cash_before - cash_after, 2) == npc_first.json()["total_cost"]

            # Creator authority is server-side and does not auto-create a rich player company.
            creator_auth = signed_headers(990001)
            creator_login = await client.post("/api/natbirzha/auth/login", headers=creator_auth)
            assert creator_login.status_code == 200
            assert creator_login.json()["user"]["is_creator"] is True
            assert creator_login.json()["has_company"] is False
            assert (await client.get("/api/natbirzha/creator/overview", headers=auth)).status_code == 403

            overview = await client.get("/api/natbirzha/creator/overview", headers=creator_auth)
            treasury_before = overview.json()["treasury_cash"]
            bond_payload = {
                "title": "P0 Bond",
                "volume": 10,
                "face_value": 1000.0,
                "coupon_rate": 5.0,
                "maturity_days": 30,
                "purpose": "P0 verification",
            }
            bond_headers = {**creator_auth, "Idempotency-Key": "creator-bond-1"}
            bond = await client.post("/api/natbirzha/creator/bonds/issue", headers=bond_headers, json=bond_payload)
            bond_replay = await client.post("/api/natbirzha/creator/bonds/issue", headers=bond_headers, json=bond_payload)
            assert bond.status_code == 200 and bond_replay.json() == bond.json()
            assert bond.json()["raised_funds"] == 0.0
            assert bond.json()["treasury_cash"] == treasury_before

        print("NATBIRZHA P0 HTTP API hardening checks: PASS")
    finally:
        nat_settings.ALLOW_TEST_AUTH = old_test_auth
        nat_settings.CREATOR_TG_IDS = old_creators


if __name__ == "__main__":
    asyncio.run(run())
