import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.db.session import async_session_factory, init_db
from backend.main import app
from backend.natbirzha.config import get_game_now, nat_settings
from backend.natbirzha.models.company import NatFactory


def create_test_init_data(user_id: int, username: str = "nat_tester") -> str:
    user_json = json.dumps(
        {"id": user_id, "first_name": "Tester", "username": username},
        separators=(",", ":"),
    )
    auth_date = str(int(time.time()))
    values = {"auth_date": auth_date, "user": user_json}
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", nat_settings.TEST_AUTH_SECRET.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    from urllib.parse import urlencode
    return urlencode(values)


async def test_vertical_playable_slice():
    nat_settings.ALLOW_TEST_AUTH = True
    await init_db()
    user_id = int(time.time()) % 1000000 + 800000
    headers = {
        "X-Telegram-Init-Data": create_test_init_data(user_id, f"magnat_steel_{user_id}"),
        "Content-Type": "application/json",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        login = await client.post("/api/natbirzha/auth/login", headers=headers)
        assert login.status_code == 200, login.text
        assert login.json()["authenticated"] is True

        create = await client.post(
            "/api/natbirzha/company/create",
            headers={**headers, "Idempotency-Key": f"create-{user_id}"},
            json={"name": f"Северсталь {user_id}", "specialization": "metallurgist"},
        )
        assert create.status_code == 200, create.text
        assert create.json()["cash"] == nat_settings.STARTING_CASH

        company = (await client.get("/api/natbirzha/company/me", headers=headers)).json()
        factory = company["factories"][0]
        assert factory["building_type"] == "steel_mill"
        assert factory["current_recipe"] is None
        factory_id = factory["id"]

        before_ore = company["inventory"].get("iron_ore", 0.0)
        before_coal = company["inventory"].get("coal", 0.0)
        buy_ore = await client.post(
            "/api/natbirzha/market/npc/trade",
            headers={**headers, "Idempotency-Key": f"ore-{user_id}"},
            json={"item_id": "iron_ore", "action": "BUY", "quantity": 10.0},
        )
        buy_coal = await client.post(
            "/api/natbirzha/market/npc/trade",
            headers={**headers, "Idempotency-Key": f"coal-{user_id}"},
            json={"item_id": "coal", "action": "BUY", "quantity": 5.0},
        )
        assert buy_ore.status_code == 200 and buy_ore.json()["unit_price"] == 43.75
        assert buy_coal.status_code == 200 and buy_coal.json()["unit_price"] == 37.50

        after_buy = (await client.get("/api/natbirzha/company/me", headers=headers)).json()
        assert after_buy["inventory"]["iron_ore"] == before_ore + 10.0
        assert after_buy["inventory"]["coal"] == before_coal + 5.0

        started = await client.post(
            f"/api/natbirzha/production/factory/{factory_id}/start",
            headers={**headers, "Idempotency-Key": f"start-{user_id}"},
            params={"recipe_id": "smelt_steel_mill"},
        )
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "running"

        duplicate = await client.post(
            f"/api/natbirzha/production/factory/{factory_id}/start",
            headers={**headers, "Idempotency-Key": f"start-second-{user_id}"},
            params={"recipe_id": "smelt_steel_mill"},
        )
        assert duplicate.status_code == 409

        early = await client.post(
            f"/api/natbirzha/production/factory/{factory_id}/collect",
            headers={**headers, "Idempotency-Key": f"early-{user_id}"},
        )
        assert early.status_code == 409

        async with async_session_factory() as session:
            fac = (await session.execute(select(NatFactory).where(NatFactory.id == factory_id))).scalar_one()
            fac.cycle_ready_at = get_game_now() - timedelta(seconds=1)
            await session.commit()

        collected = await client.post(
            f"/api/natbirzha/production/factory/{factory_id}/collect",
            headers={**headers, "Idempotency-Key": f"collect-{user_id}"},
        )
        assert collected.status_code == 200, collected.text
        steel_output = collected.json()["outputs_produced"]["steel"]
        assert steel_output == 1.5

        state_after = (await client.get("/api/natbirzha/company/me", headers=headers)).json()
        assert state_after["inventory"]["iron_ore"] == after_buy["inventory"]["iron_ore"] - 2.0
        assert state_after["inventory"]["coal"] == after_buy["inventory"]["coal"] - 1.0
        assert state_after["inventory"]["steel"] == steel_output

        cash_before = state_after["cash"]
        sell_headers = {**headers, "Idempotency-Key": f"sell-steel-{user_id}"}
        sold = await client.post(
            "/api/natbirzha/market/npc/trade",
            headers=sell_headers,
            json={"item_id": "steel", "action": "SELL", "quantity": 1.0},
        )
        assert sold.status_code == 200 and sold.json()["unit_price"] == 72.0
        cash_after = (await client.get("/api/natbirzha/company/me", headers=headers)).json()["cash"]
        assert round(cash_after - cash_before, 2) == 72.0

        replay = await client.post(
            "/api/natbirzha/market/npc/trade",
            headers=sell_headers,
            json={"item_id": "steel", "action": "SELL", "quantity": 1.0},
        )
        assert replay.status_code == 200
        final_cash = (await client.get("/api/natbirzha/company/me", headers=headers)).json()["cash"]
        assert final_cash == cash_after

    print("NATBIRZHA vertical playable slice: PASS")


if __name__ == "__main__":
    asyncio.run(test_vertical_playable_slice())
