import os
import sys
import os
import pytest
import asyncio
import json
import hmac
import hashlib
import time
from datetime import datetime, timedelta

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from backend.main import app
from backend.db.session import init_db, async_session_factory
from backend.natbirzha.config import nat_settings, get_game_today, get_game_now
from backend.natbirzha.services.stock_service import StockService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.military_service import MilitaryService
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.models.military import NatTournament, NatTournamentParticipant
from backend.natbirzha.models.stocks import NatDividendPayment


def create_test_init_data(user_id: int, username: str = "nat_tester") -> str:
    user_data = {"id": user_id, "first_name": "Tester", "username": username}
    user_json = json.dumps(user_data, separators=(',', ':'))
    auth_date = str(int(time.time()))
    params = [f"auth_date={auth_date}", f"user={user_json}"]
    data_check_string = "\n".join(sorted(params))
    secret_key = hmac.new(b"WebAppData", nat_settings.TEST_AUTH_SECRET.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return f"auth_date={auth_date}&user={user_json}&hash={calc_hash}"


async def test_idempotency_and_stocks():
    nat_settings.ALLOW_TEST_AUTH = True
    print("\n" + "=" * 64)
    print("📈 TESTING IDEMPOTENCY 409, IPO, DIVIDENDS & TOURNAMENT TIE-BREAKER")
    print("=" * 64)

    await init_db()

    # 1. Idempotency HTTP 409 Conflict check
    print("\n--- [1/4] Idempotency Key Conflict on Altered Payload (HTTP 409) ---")
    u_id = int(time.time()) % 1000000 + 600000
    init_data = create_test_init_data(u_id, f"trader_{u_id}")
    headers = {"X-Telegram-Init-Data": init_data, "Content-Type": "application/json"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create company
        await client.post(
            "/api/natbirzha/company/create",
            headers=headers,
            json={"name": f"Холдинг {u_id}", "specialization": "power_engineer"}
        )

        idemp_key = f"idemp-conflict-test-{u_id}"
        # Request 1: Trade 5 units of energy
        r1 = await client.post(
            "/api/natbirzha/market/npc/trade",
            headers={**headers, "Idempotency-Key": idemp_key},
            json={"item_id": "energy", "action": "buy", "quantity": 5.0}
        )
        assert r1.status_code == 200, f"R1 failed: {r1.text}"

        # Request 2: Altered payload with same Idempotency-Key -> MUST return HTTP 409 Conflict
        r2 = await client.post(
            "/api/natbirzha/market/npc/trade",
            headers={**headers, "Idempotency-Key": idemp_key},
            json={"item_id": "energy", "action": "buy", "quantity": 10.0}
        )
        assert r2.status_code == 409, f"Expected 409 Conflict, got {r2.status_code}: {r2.text}"
        print("[OK] Reusing Idempotency-Key with altered payload strictly returned HTTP 409 Conflict.")

    # 2. Stock IPO Issuance (Founder 60%, Float 40%)
    print("\n--- [2/4] IPO Issuance & Share Allocation ---")
    async with async_session_factory() as session:
        u_ipo = int(time.time()) % 1000000 + 500000
        comp_ipo = await CompanyService.create_company(session, u_ipo, f"ПАО Энергия {u_ipo}", "power_engineer")
        comp_ipo.level = 2  # IPO requires level >= 2

        stock = await StockService.apply_for_ipo(session, comp_ipo)
        assert stock.total_shares == nat_settings.IPO_MIN_SHARES
        assert stock.founder_shares == int(nat_settings.IPO_MIN_SHARES * 0.60), "Founder must retain 60% of shares"
        assert stock.float_shares == int(nat_settings.IPO_MIN_SHARES * 0.40), "Public float must be 40% of shares"
        assert stock.is_listed is True
        print(f"[OK] IPO issued for company {comp_ipo.id}: {stock.total_shares} total shares ({stock.founder_shares} founder, {stock.float_shares} float).")

    # 3. Dividend Distribution (default 5% closed profit pool)
    print("\n--- [3/4] Daily Distributable Dividend Pool & Settlement ---")
    async with async_session_factory() as session:
        today = get_game_today()
        # Record closed cash profit of 50,000 cash for today
        fin = NatDailyFinancials(
            company_id=comp_ipo.id,
            calendar_date=today,
            gross_revenue=50000.0,
            opex=0.0,
            closed_profit=50000.0,
            developer_fee_paid=0.0,
            created_at=get_game_now()
        )
        session.add(fin)
        await session.commit()

        # Distribute daily dividends
        res_div = await DividendService.settle_daily_dividends_for_stock(session, stock, today)
        assert res_div["status"] == "settled"
        assert res_div["closed_profit"] == 50000.0
        assert res_div["dividend_pool"] == 2500.0, "Default dividend pool must be 5% (2,500 cash)"
        payment = await session.scalar(select(NatDividendPayment).where(
            NatDividendPayment.stock_id == stock.id,
            NatDividendPayment.holder_company_id == comp_ipo.id,
        ))
        assert payment is not None and payment.payout_cash > 0
        print(f"[OK] 5% default dividend pool (2,500 cash) settled for {today} @ {res_div['per_share']} cash/share.")

    # 4. Tournament Deterministic Tie-Breaker (Earliest Timestamp)
    print("\n--- [4/4] 72h Tournament Deterministic Earliest-Timestamp Tie-Breaker ---")
    async with async_session_factory() as session:
        now = get_game_now()
        tourn_num = int(time.time()) % 1000000 + 1
        tourn = NatTournament(
            tournament_number=tourn_num,
            start_time=now,
            snapshot_time=now + timedelta(hours=71, minutes=45),
            finish_time=now + timedelta(hours=72),
            prize_pool_nat=100,
            status="SNAPSHOT"
        )
        session.add(tourn)
        await session.flush()

        # Create 2nd test company
        u_comp2 = int(time.time()) % 1000000 + 400000
        comp2 = await CompanyService.create_company(session, u_comp2, f"УралМаш {u_comp2}", "metallurgist")

        # Two participants with identical strength (500) but different timestamps
        p_early = NatTournamentParticipant(
            tournament_id=tourn.id,
            company_id=comp_ipo.id,
            snapshot_strength=500,
            army_updated_at=now - timedelta(minutes=30)
        )
        p_late = NatTournamentParticipant(
            tournament_id=tourn.id,
            company_id=comp2.id,
            snapshot_strength=500,
            army_updated_at=now - timedelta(minutes=5)
        )
        session.add_all([p_early, p_late])
        await session.commit()

        # Resolve tournament: Earliest-Timestamp tie-breaker must declare p_early as #1 winner
        res_tourn = await MilitaryService.resolve_tournament(session, tourn.id)
        assert res_tourn["status"] == "completed"
        assert res_tourn["winner_company_id"] == comp_ipo.id, "Earlier timestamp must win the tie-break!"
        assert res_tourn["prize_awarded_nat"] == 100, "Winner must receive 100 NAT prize"

        # Verify company NAT balance updated
        winner_comp = await session.get(NatCompany, comp_ipo.id)
        assert winner_comp.nat_balance == 100
        print(f"[OK] Tie-breaker resolved: Company {winner_comp.id} (earlier timestamp) won 100 NAT!")

    print("\n" + "=" * 64)
    print("🎉 ALL IDEMPOTENCY, STOCKS & TOURNAMENT TESTS PASSED PERFECTLY!")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    asyncio.run(test_idempotency_and_stocks())
