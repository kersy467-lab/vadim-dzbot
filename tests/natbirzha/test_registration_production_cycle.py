import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/natbirzha_cycle_test.db")
os.environ.setdefault("BOT_TOKEN", "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
os.environ.setdefault("ENABLE_BOT_POLLING", "false")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.db.models import Base
from backend.db.session import async_session_factory, engine, init_db
from backend.main import app
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.production_service import ProductionTickEngine


def headers(tg_id: int) -> dict:
    nat_settings.ALLOW_TEST_AUTH = True
    data = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": tg_id, "first_name": "CycleTester"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", nat_settings.TEST_AUTH_SECRET.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urllib.parse.urlencode(data)}


async def main():
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        auth = headers(991001)
        assert (await client.post("/api/natbirzha/auth/login", headers=auth)).status_code == 200
        created = await client.post(
            "/api/natbirzha/company/create",
            headers={**auth, "Idempotency-Key": "cycle-company-create"},
            json={"name": "Нефтегаз Тест", "specialization": "oil_gas"},
        )
        assert created.status_code == 200, created.text
        assert created.json()["specialization"] == "oilman"

        status = await client.get("/api/natbirzha/production/factories", headers=auth)
        factory = status.json()["factories"][0]
        assert factory["building_type"] == "oil_rig", factory
        assert factory["current_recipe"] is None, factory
        assert factory["default_recipe"] == "pump_oil_crude", factory
        assert factory["start_hint"]["reason"] == "ready", factory
        assert factory["start_hint"]["next_action"] == "start_cycle", factory

        started = await client.post(
            "/api/natbirzha/production/factory/produce",
            headers={**auth, "Idempotency-Key": "cycle-start-1"},
            json={"factory_id": factory["id"], "recipe_id": "pump_oil_crude"},
        )
        assert started.status_code == 200 and started.json()["status"] == "running", started.text
        assert started.json()["duration_seconds"] >= 15

        inventory = (await client.get("/api/natbirzha/production/inventory", headers=auth)).json()["inventory"]
        assert not any(row["item_id"] == "oil_crude" and row["quantity"] > 0 for row in inventory)

        async with async_session_factory() as session:
            fac = (await session.execute(select(NatFactory).where(NatFactory.id == factory["id"]))).scalar_one()
            company = (await session.execute(select(NatCompany).where(NatCompany.id == fac.company_id))).scalar_one()
            result = await ProductionTickEngine.complete_cycle(session, company, fac, fac.cycle_ready_at)
            assert result["success"]
            await session.commit()

        inventory_after = (await client.get("/api/natbirzha/production/inventory", headers=auth)).json()["inventory"]
        assert any(row["item_id"] == "oil_crude" and row["quantity"] > 0 for row in inventory_after)

    print("NATBIRZHA registration + timed production cycle: PASS")


if __name__ == "__main__":
    asyncio.run(main())
