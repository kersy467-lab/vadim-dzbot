import os
import sys
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_rpg_admin.db"

from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.db.session import init_db
from backend.db.models import Base


async def run_admin_api_suite():
    await init_db()
    headers = {"X-Telegram-User-Id": "7755842535"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. GET /api/rpg/admin/players
        r = await client.get("/api/rpg/admin/players", headers=headers)
        assert r.status_code == 200, f"admin players failed: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert len(data.get("players", [])) > 0
        print(f"[OK] GET /api/rpg/admin/players: {len(data['players'])} players")

        # 2. GET /api/rpg/admin/items_catalog
        r = await client.get("/api/rpg/admin/items_catalog", headers=headers)
        assert r.status_code == 200, f"admin items catalog failed: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert len(data.get("items", [])) >= 20
        print(f"[OK] GET /api/rpg/admin/items_catalog: {len(data['items'])} items")

        # 3. POST /api/rpg/admin/give_gold
        r = await client.post("/api/rpg/admin/give_gold", json={"target": "7755842535", "amount": 100000}, headers=headers)
        assert r.status_code == 200, f"admin give gold failed: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("gold") >= 100000
        assert data["profile"]["is_admin"] is True
        print(f"[OK] POST /api/rpg/admin/give_gold: new balance {data['gold']}")

        # 4. POST /api/rpg/admin/give_gems
        r = await client.post("/api/rpg/admin/give_gems", json={"target": "7755842535", "amount": 500}, headers=headers)
        assert r.status_code == 200, f"admin give gems failed: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("gems") >= 500
        print(f"[OK] POST /api/rpg/admin/give_gems: new gems {data['gems']}")

        # 5. POST /api/rpg/admin/set_level
        r = await client.post("/api/rpg/admin/set_level", json={"target": "7755842535", "level": 30}, headers=headers)
        assert r.status_code == 200, f"admin set level failed: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("level") == 30
        assert data["profile"]["level"] == 30
        print(f"[OK] POST /api/rpg/admin/set_level: level set to {data['level']}")

        # 6. POST /api/rpg/admin/give_item
        r = await client.post("/api/rpg/admin/give_item", json={"target": "7755842535", "rarity": "legendary", "level": 20}, headers=headers)
        assert r.status_code == 200, f"admin give item failed: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("item") is not None
        print(f"[OK] POST /api/rpg/admin/give_item: item granted {data['item']['name']}")

        # 7. POST /api/rpg/admin/reset_player
        r = await client.post("/api/rpg/admin/reset_player", json={"target": "7755842535"}, headers=headers)
        assert r.status_code == 200, f"admin reset failed: {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data["profile"]["level"] == 1
        print(f"[OK] POST /api/rpg/admin/reset_player: player reset to level {data['profile']['level']}")

        # 8. Test admin slot 999001
        slot_headers = {"X-Telegram-User-Id": "999001"}
        r = await client.get("/api/rpg/profile", headers=slot_headers)
        assert r.status_code == 200, f"profile slot failed: {r.text}"
        print("[OK] Test slot 999001 accessed /api/rpg/profile successfully!")

    print("\n=== ALL NATARGRP ADMIN BACKEND ENDPOINTS PASSED! ===")


if __name__ == "__main__":
    asyncio.run(run_admin_api_suite())
