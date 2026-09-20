import os
import sys
import asyncio
import time
from datetime import datetime, timedelta

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx
from sqlalchemy import select

from backend.main import app
from backend.db.session import async_session_factory, init_db
from backend.db.models import User
from backend.natbirzha.config import nat_settings, get_game_now, get_game_today, normalize_dt
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.military import NatTournament, NatTournamentParticipant
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.stock_service import StockService
from backend.natbirzha.services.military_service import MilitaryService
from backend.natbirzha.services.bankruptcy_service import BankruptcyService


def make_test_auth_headers(tg_id: int) -> dict:
    import hashlib, hmac, json, urllib.parse, time as _time
    payload = {"id": tg_id, "first_name": f"Tester{tg_id}"}
    data = {"auth_date": str(int(_time.time())), "user": json.dumps(payload, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", nat_settings.TEST_AUTH_SECRET.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Telegram-Init-Data": urllib.parse.urlencode(data)}


async def test_audit_fixes():
    nat_settings.ALLOW_TEST_AUTH = True
    await init_db()
    print("\n================================================================")
    print("🛡️ RUNNING AUDIT FIXES COMPREHENSIVE VERIFICATION")
    print("================================================================")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # [1] Datetime Timezone Resilience & Offline Catch-up DB Commit
        print("\n--- [1/6] Timezone Resilience & Offline Catch-Up Commit Verification ---")
        tg_id_1 = int(time.time()) % 1000000 + 800000
        headers_1 = make_test_auth_headers(tg_id_1)

        # Login to create user
        login_res = await client.post("/api/natbirzha/auth/login", headers=headers_1)
        assert login_res.status_code == 200

        # Create power company (hydro_solar requires NO inputs!)
        create_res = await client.post(
            "/api/natbirzha/company/create",
            headers=headers_1,
            json={"name": f"РусГидро {tg_id_1}", "specialization": "power_engineer"}
        )
        assert create_res.status_code == 200
        company_id = create_res.json()["company_id"]
        assert create_res.json()["specialization"] == "power_engineer"
        status = await client.get("/api/natbirzha/company/me", headers=headers_1)
        assert status.status_code == 200
        assert status.json()["specialization"] == "power_engineer"

        # Explicitly start a real cycle first. Offline catch-up may only finish
        # cycles that were already started; it must never invent background ticks.
        factories_res = await client.get("/api/natbirzha/production/factories", headers=headers_1)
        factory_id = factories_res.json()["factories"][0]["id"]
        start_res = await client.post(
            f"/api/natbirzha/production/factory/{factory_id}/start",
            headers={**headers_1, "Idempotency-Key": f"offline-start-{tg_id_1}"},
            params={"recipe_id": "generate_solar"},
        )
        assert start_res.status_code == 200, start_res.text

        # Simulate the player being offline past ready_at.
        async with async_session_factory() as session:
            fac_res = await session.execute(select(NatFactory).where(NatFactory.id == factory_id))
            factory = fac_res.scalar_one()
            factory.cycle_ready_at = (get_game_now() - timedelta(seconds=5)).replace(tzinfo=None)
            await session.commit()

        # Login again: catch_up_company completes only that explicitly started cycle.
        login_again = await client.post("/api/natbirzha/auth/login", headers=headers_1)
        assert login_again.status_code == 200

        async with async_session_factory() as session:
            inv_res = await session.execute(
                select(NatInventory).where(
                    NatInventory.company_id == company_id,
                    NatInventory.item_id == "energy"
                )
            )
            inv = inv_res.scalar_one_or_none()
            assert inv is not None and inv.quantity > 0
            fac = (await session.execute(select(NatFactory).where(NatFactory.id == factory_id))).scalar_one()
            assert fac.current_recipe is None and fac.cycle_ready_at is None
            print(f"[OK] Offline catch-up completed one explicitly started cycle: {inv.quantity} energy.")

        # [2] Dynamic is_public in /company/me after IPO
        print("\n--- [2/6] Dynamic is_public Verification on IPO ---")
        # IPO eligibility is intentionally level-gated. This test verifies the
        # public-status transition, so prepare an eligible company explicitly.
        async with async_session_factory() as session:
            company = await session.get(NatCompany, company_id)
            company.level = nat_settings.IPO_MIN_LEVEL
            await session.commit()
        status_pre = await client.get("/api/natbirzha/company/me", headers=headers_1)
        assert status_pre.status_code == 200
        assert status_pre.json()["is_public"] is False

        # Apply for IPO
        ipo_res = await client.post("/api/natbirzha/stocks/ipo/apply", headers=headers_1, json={})
        assert ipo_res.status_code == 200, ipo_res.text
        stock_id = ipo_res.json()["stock_id"]

        status_post = await client.get("/api/natbirzha/company/me", headers=headers_1)
        assert status_post.status_code == 200
        assert status_post.json()["is_public"] is True, "Company must show is_public=True after IPO"
        print("[OK] /company/me correctly reflects is_public=True after IPO issuance.")

        # [3] Secondary Stock Buying & Selling
        print("\n--- [3/6] Secondary Stock Market (Buy & Sell) Verification ---")
        tg_id_2 = int(time.time()) % 1000000 + 850000
        headers_2 = make_test_auth_headers(tg_id_2)
        await client.post("/api/natbirzha/auth/login", headers=headers_2)
        await client.post(
            "/api/natbirzha/company/create",
            headers=headers_2,
            json={"name": f"ИнвестКапитал {tg_id_2}", "specialization": "technoprom"}
        )

        # Company 2 buys 500 shares of Company 1
        buy_res = await client.post(
            "/api/natbirzha/stocks/buy",
            headers=headers_2,
            json={"stock_id": stock_id, "shares_count": 500}
        )
        assert buy_res.status_code == 200
        assert buy_res.json()["shares_bought"] == 500

        # The public quote must expose the remaining free-float supply. Buying
        # 500 of the initial 4,000 shares cannot leave the quote unchanged.
        market_after_buy = await client.get("/api/natbirzha/stocks/market")
        assert market_after_buy.status_code == 200
        listed_after_buy = next(row for row in market_after_buy.json()["stocks"] if row["stock_id"] == stock_id)
        assert listed_after_buy["float_shares"] == 3500

        # Company 2 checks portfolio
        port_res = await client.get("/api/natbirzha/stocks/portfolio", headers=headers_2)
        assert port_res.status_code == 200
        assert len(port_res.json()["portfolio"]) == 1
        assert port_res.json()["portfolio"][0]["shares_count"] == 500

        # Company 2 sells 200 shares back to the market
        sell_res = await client.post(
            "/api/natbirzha/stocks/sell",
            headers=headers_2,
            json={"stock_id": stock_id, "shares_count": 200}
        )
        assert sell_res.status_code == 200
        assert sell_res.json()["shares_sold"] == 200
        assert sell_res.json()["remaining_shares"] == 300
        market_after_sell = await client.get("/api/natbirzha/stocks/market")
        listed_after_sell = next(row for row in market_after_sell.json()["stocks"] if row["stock_id"] == stock_id)
        assert listed_after_sell["float_shares"] == 3700
        unified_portfolio = await client.get("/api/natbirzha/portfolio", headers=headers_2)
        assert unified_portfolio.status_code == 200
        portfolio_payload = unified_portfolio.json()
        assert {"summary", "stocks", "bonds", "instruments", "dividend_payments"}.issubset(portfolio_payload)
        assert portfolio_payload["stocks"][0]["shares_count"] == 300
        print("[OK] Secondary stock market buy and sell executed flawlessly.")

        # [4] Tournament Endpoint & cycle_number AttributeError Fix
        print("\n--- [4/6] Tournament Resolution & cycle_number Verification ---")
        async with async_session_factory() as session:
            now = get_game_now()
            t_num = int(time.time()) % 1000000 + 777000
            tourn = NatTournament(
                tournament_number=t_num,
                start_time=now,
                snapshot_time=now + timedelta(hours=71),
                finish_time=now + timedelta(hours=72),
                prize_pool_nat=100,
                status="PENDING"
            )
            session.add(tourn)
            await session.commit()

        tourn_res = await client.get("/api/natbirzha/military/tournaments/current", headers=headers_1)
        assert tourn_res.status_code == 200
        t_data = tourn_res.json()["tournament"]
        assert t_data is not None
        assert t_data["cycle_number"] == t_num
        print(f"[OK] Tournament fetched without AttributeError: cycle_number={t_data['cycle_number']}.")

        # [5] Alliance Lifecycle (Create, Inspect, Join, Leave)
        print("\n--- [5/6] Alliance Lifecycle Verification ---")
        alliance_name = f"Уральский Альянс {tg_id_1}"
        create_all_res = await client.post(
            "/api/natbirzha/alliance/create",
            headers=headers_1,
            json={"name": alliance_name}
        )
        assert create_all_res.status_code == 200
        alliance_id = create_all_res.json()["alliance_id"]

        my_all_res = await client.get("/api/natbirzha/alliance/my", headers=headers_1)
        assert my_all_res.status_code == 200
        assert my_all_res.json()["in_alliance"] is True
        assert my_all_res.json()["alliance"]["name"] == alliance_name
        assert my_all_res.json()["alliance"]["my_role"] == "LEADER"

        # Company 2 joins alliance
        join_all_res = await client.post(
            "/api/natbirzha/alliance/join",
            headers=headers_2,
            json={"alliance_id": alliance_id}
        )
        assert join_all_res.status_code == 200
        assert join_all_res.json()["member_count"] == 2

        # Company 2 leaves alliance
        leave_res = await client.post("/api/natbirzha/alliance/leave", headers=headers_2)
        assert leave_res.status_code == 200
        print("[OK] Alliance creation, inspection, joining, and leaving verified 100%.")

        # [6] Scheduler Hourly Tick Result Structure
        print("\n--- [6/6] Scheduler Hourly Tick Verification ---")
        async with async_session_factory() as session:
            tick_res = await ProductionTickEngine.process_global_scheduled_tick(session)
            assert isinstance(tick_res, dict)
            assert "ticks_processed" in tick_res
            assert tick_res.get("ticks_processed") >= 0
            print(f"[OK] process_global_scheduled_tick returns structured dict: {tick_res}.")

    print("\n================================================================")
    print("🎉 ALL AUDIT FIXES VERIFIED SUCCESSFULLY WITH ZERO ERRORS!")
    print("================================================================\n")


if __name__ == "__main__":
    asyncio.run(test_audit_fixes())
