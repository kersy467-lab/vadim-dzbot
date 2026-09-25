import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from urllib.parse import urlencode

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.session import async_session_factory, init_db
from backend.main import app
from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.building_catalog import CANONICAL_BUILDINGS
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.recipes import RECIPES, validate_recipe_dag


def signed_headers(tg_id: int, username: str) -> dict:
    data = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": tg_id, "username": username, "first_name": username}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", nat_settings.TEST_AUTH_SECRET.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urlencode(data)}


@pytest.mark.asyncio
async def test_full_part1_and_creator_checklist():
    await init_db()
    nat_settings.ALLOW_TEST_AUTH = True
    admin_tg = 1053722876
    player_tg = int(time.time()) % 1000000 + 777000
    nat_settings.CREATOR_TG_IDS = str(admin_tg)

    # 1. Expanded progression keeps at least 10 enterprises per each of 8 industries,
    # and every canonical enterprise has exactly one active canonical recipe.
    assert len(CANONICAL_BUILDINGS) >= 80
    # Alternate recipes add valid production paths; every building still has
    # exactly one canonical/default recipe id.
    assert len(RECIPES) >= len(CANONICAL_BUILDINGS)
    assert len(set(RECIPES)) == len(RECIPES)
    for building_id, spec in CANONICAL_BUILDINGS.items():
        assert spec["id"] == building_id
        assert spec["recipe_id"] in RECIPES
        assert RECIPES[spec["recipe_id"]]["factory_type"] == building_id
    assert validate_recipe_dag() is True

    # 2. Creator treasury is separate from company cash: all player companies use same grant.
    async with async_session_factory() as session:
        uid_regular = int(time.time()) % 1000000 + 910000
        uid_creator = uid_regular + 1
        regular = await CompanyService.create_company(session, uid_regular, f"Reg Corp {uid_regular}", "miner")
        creator_company = await CompanyService.create_company(session, uid_creator, f"Creator Corp {uid_creator}", "metallurgist")
        assert regular.cash == nat_settings.STARTING_CASH
        assert creator_company.cash == nat_settings.STARTING_CASH

    auth_admin = signed_headers(admin_tg, "creator")
    auth_player = signed_headers(player_tg, "player")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. Unsigned payload is rejected; signed player can create/reset company.
        unsigned = {"X-Telegram-Init-Data": "user=%7B%22id%22%3A777888%7D"}
        assert (await client.post("/api/natbirzha/auth/login", headers=unsigned)).status_code == 401
        assert (await client.post("/api/natbirzha/auth/login", headers=auth_player)).status_code == 200

        create = await client.post(
            "/api/natbirzha/company/create",
            json={"name": f"TempCorp {player_tg}", "specialization": "forester"},
            headers={**auth_player, "Idempotency-Key": f"create-{player_tg}"},
        )
        assert create.status_code == 200, create.text
        reset_headers = {**auth_player, "Idempotency-Key": f"reset-{player_tg}"}
        reset = await client.post("/api/natbirzha/company/reset", headers=reset_headers)
        assert reset.status_code == 200 and reset.json()["success"] is True
        assert (await client.get("/api/natbirzha/company/me", headers=auth_player)).status_code == 404

        # Recreate for market checks.
        create = await client.post(
            "/api/natbirzha/company/create",
            json={"name": f"TraderCorp {player_tg}", "specialization": "metallurgist"},
            headers={**auth_player, "Idempotency-Key": f"create2-{player_tg}"},
        )
        assert create.status_code == 200
        company_id = create.json()["company_id"]

        # 4. Regular player cannot use Creator routes.
        forbidden = await client.get("/api/natbirzha/creator/overview", headers=auth_player)
        assert forbidden.status_code == 403

        # 5. Creator gets State dashboard; bond issuance must NOT mint treasury cash.
        assert (await client.post("/api/natbirzha/auth/login", headers=auth_admin)).status_code == 200
        overview = await client.get("/api/natbirzha/creator/overview", headers=auth_admin)
        assert overview.status_code == 200
        treasury_before = overview.json()["treasury_cash"]
        bond = await client.post(
            "/api/natbirzha/creator/bonds/issue",
            headers={**auth_admin, "Idempotency-Key": "bond-checklist-1"},
            json={
                "title": "ОФЗ-НАТ-1",
                "volume": 500,
                "face_value": 1000.0,
                "coupon_rate": 8.5,
                "maturity_days": 30,
                "purpose": "Резерв энергосети",
            },
        )
        assert bond.status_code == 200, bond.text
        assert bond.json()["raised_funds"] == 0.0
        assert bond.json()["treasury_cash"] == treasury_before

        # 6. State price restriction is enforced on every market mutation.
        warning = await client.post(
            "/api/natbirzha/creator/market/warnings",
            headers={**auth_admin, "Idempotency-Key": "warning-checklist-1"},
            json={"company_id": company_id, "reason": "Попытка демпинга"},
        )
        assert warning.status_code == 200
        restriction = await client.post(
            "/api/natbirzha/creator/market/restrictions",
            headers={**auth_admin, "Idempotency-Key": "restriction-checklist-1"},
            json={"item_id": "iron_ore", "min_price": 50.0, "max_price": 150.0, "reason": "Стабилизация цен"},
        )
        assert restriction.status_code == 200
        restriction_id = restriction.json()["restriction_id"]

        bad_order = await client.post(
            "/api/natbirzha/market/orders/create",
            headers={**auth_player, "Idempotency-Key": "bad-order-checklist-1"},
            json={"item_id": "iron_ore", "order_type": "BUY", "price": 20.0, "quantity": 5.0},
        )
        assert bad_order.status_code == 400
        good_order = await client.post(
            "/api/natbirzha/market/orders/create",
            headers={**auth_player, "Idempotency-Key": "good-order-checklist-1"},
            json={"item_id": "iron_ore", "order_type": "BUY", "price": 100.0, "quantity": 2.0},
        )
        assert good_order.status_code == 200
        assert (await client.delete(f"/api/natbirzha/creator/market/restrictions/{restriction_id}", headers=auth_admin)).status_code == 200

        # 7. Creator audit captures the actions above.
        audit = await client.get("/api/natbirzha/creator/audit-log", headers=auth_admin)
        assert audit.status_code == 200
        actions = {row["action"] for row in audit.json()["logs"]}
        assert {"BOND_ISSUANCE", "WARNING_ISSUED", "RESTRICTION_SET"}.issubset(actions)

    print("NATBIRZHA full checklist core + creator boundaries: PASS")


if __name__ == "__main__":
    asyncio.run(test_full_part1_and_creator_checklist())
