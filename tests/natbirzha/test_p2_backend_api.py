"""P2 HTTP security and idempotency through real FastAPI dependency wiring."""

import asyncio
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.models.combat import NatArmyUnit, NatBattle
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatTournament, NatTournamentParticipant
from backend.natbirzha.config import get_game_now
from backend.natbirzha.services.auth_service import get_current_company, get_strict_natbirzha_user
from backend.natbirzha.services.premium_service import PremiumService
from backend.natbirzha.services.reference_instrument_service import ReferenceInstrumentService
from backend.natbirzha.services.state_bond_service import StateBondService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        users = [
            User(tg_id=980001, full_name="Player One", role="student", is_tester=True),
            User(tg_id=980002, full_name="Player Two", role="student", is_tester=True),
        ]
        session.add_all(users)
        await session.flush()
        companies = [
            NatCompany(user_id=users[0].id, name="API Corp One", specialization="miner"),
            NatCompany(user_id=users[1].id, name="API Corp Two", specialization="agrarian"),
        ]
        session.add_all(companies)
        await session.flush()
        session.add_all(
            [
                NatArmyUnit(company_id=companies[0].id, unit_type="infantry", quantity=100),
                NatArmyUnit(company_id=companies[1].id, unit_type="infantry", quantity=100),
            ]
        )
        await PremiumService.apply_pvc(
            session, companies[0].id, 500, "test_credit", "api-credit", {}
        )
        now = datetime(2026, 9, 19, 15, 0, 0)
        stale = NatTournament(
            tournament_number=1,
            start_time=now - timedelta(days=1),
            snapshot_time=now - timedelta(days=1),
            finish_time=now - timedelta(hours=1),
            status="COMPLETED",
            prize_pool_nat=0,
        )
        session.add(stale)
        await session.flush()
        for company in companies:
            session.add(
                NatTournamentParticipant(
                    tournament_id=stale.id,
                    company_id=company.id,
                    snapshot_strength=1000,
                    initial_strength=1000,
                    final_strength=1000,
                    army_updated_at=now,
                )
            )
        private_battle = NatBattle(
            operation_key="private-battle",
            mode="PVE",
            attacker_company_id=companies[0].id,
            seed_digest="a" * 64,
            summary_json={"battle_id": 1, "private": True},
            status="RESOLVED",
        )
        session.add(private_battle)
        rate_now = get_game_now()
        await ReferenceInstrumentService.store_rates(
            session,
            {code: (value, rate_now) for code, value in {
                "USD": 100.0, "EUR": 120.0, "GOLD": 8_000.0, "SILVER": 90.0,
            }.items()},
            fetched_at=rate_now,
        )
        bond = await StateBondService.issue(
            session, 777, "API Bond", 10, 1000, 10, 30, "API test", commit=False
        )
        await StateBondService.buy(session, companies[0], bond["bond_id"], 4, commit=False)
        await session.commit()
        user_ids = [user.id for user in users]
        company_ids = [company.id for company in companies]
        stale_id = stale.id
        battle_id = private_battle.id
        bond_id = bond["bond_id"]

    app = FastAPI()
    app.include_router(natbirzha_router, prefix="/api")

    async def test_session():
        async with sessions() as session:
            yield session

    async def test_user(
        x_test_user: int | None = Header(None, alias="X-Test-User"),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if x_test_user is None:
            raise HTTPException(status_code=401, detail="Missing test identity")
        user = await session.scalar(select(User).where(User.id == x_test_user))
        if user is None:
            raise HTTPException(status_code=401, detail="Unknown test identity")
        return user

    async def test_company(
        user: User = Depends(get_strict_natbirzha_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> NatCompany:
        company = await session.scalar(select(NatCompany).where(NatCompany.user_id == user.id))
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return company

    app.dependency_overrides[get_db_session] = test_session
    app.dependency_overrides[get_strict_natbirzha_user] = test_user
    app.dependency_overrides[get_current_company] = test_company

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unsigned = await client.get("/api/natbirzha/premium/wallet")
        assert unsigned.status_code == 401

        headers_one = {"X-Test-User": str(user_ids[0])}
        wallet = await client.get("/api/natbirzha/premium/wallet", headers=headers_one)
        assert wallet.status_code == 200 and wallet.json()["balance"] == 500

        missing_key = await client.post(
            "/api/natbirzha/premium/licenses/rare_mining/purchase", headers=headers_one
        )
        assert missing_key.status_code == 400
        buy_headers = {**headers_one, "Idempotency-Key": "api-license-1"}
        first = await client.post(
            "/api/natbirzha/premium/licenses/rare_mining/purchase", headers=buy_headers
        )
        second = await client.post(
            "/api/natbirzha/premium/licenses/rare_mining/purchase", headers=buy_headers
        )
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert first.json()["balance"] == 380

        forged_creator = await client.post(
            "/api/natbirzha/creator/tournaments/launch",
            headers={**headers_one, "Idempotency-Key": "forged-admin"},
            json={"reward_first_pvc": 999, "reward_second_pvc": 999, "reward_third_pvc": 999},
        )
        assert forged_creator.status_code == 403

        stale_attack = await client.post(
            f"/api/natbirzha/military/tournaments/{stale_id}/targets/{company_ids[1]}/attack",
            headers={**headers_one, "Idempotency-Key": "stale-pvp"},
        )
        assert stale_attack.status_code == 400
        assert stale_attack.json()["detail"]["reason"] == "tournament_not_active"

        tournament_state = await client.get(
            "/api/natbirzha/military/tournaments/current", headers=headers_one
        )
        assert tournament_state.status_code == 200
        finish_time = datetime.fromisoformat(tournament_state.json()["tournament"]["finish_time"])
        assert finish_time.utcoffset() is not None, "Browser-facing tournament timestamps need an offset"

        tournament_history = await client.get(
            "/api/natbirzha/military/tournaments/history", headers=headers_one
        )
        assert tournament_history.status_code == 200
        assert tournament_history.json()["tournaments"][0]["tournament_id"] == stale_id
        assert tournament_history.json()["tournaments"][0]["my_participation"]["company_id"] == company_ids[0]

        missing_pve_key = await client.post(
            "/api/natbirzha/military/pve/targets/local_logistics/attack", headers=headers_one
        )
        assert missing_pve_key.status_code == 400

        other_user = {"X-Test-User": str(user_ids[1])}
        private = await client.get(
            f"/api/natbirzha/military/battles/{battle_id}", headers=other_user
        )
        assert private.status_code == 404

        instruments = await client.get("/api/natbirzha/instruments", headers=headers_one)
        assert instruments.status_code == 200
        assert {row["code"] for row in instruments.json()["instruments"]} == {"USD", "EUR", "GOLD", "SILVER"}
        missing_trade_key = await client.post(
            "/api/natbirzha/instruments/trade", headers=headers_one,
            json={"instrument_code": "USD", "side": "buy", "quantity": 2},
        )
        assert missing_trade_key.status_code == 400
        trade_headers = {**headers_one, "Idempotency-Key": "instrument-buy-1"}
        trade_one = await client.post(
            "/api/natbirzha/instruments/trade", headers=trade_headers,
            json={"instrument_code": "USD", "side": "buy", "quantity": 2},
        )
        trade_replay = await client.post(
            "/api/natbirzha/instruments/trade", headers=trade_headers,
            json={"instrument_code": "USD", "side": "buy", "quantity": 2},
        )
        assert trade_one.status_code == 200 and trade_replay.json() == trade_one.json()

        list_headers = {**headers_one, "Idempotency-Key": "bond-list-1"}
        listing = await client.post(
            "/api/natbirzha/bonds/listings", headers=list_headers,
            json={"bond_id": bond_id, "quantity": 2, "unit_price": 1100},
        )
        assert listing.status_code == 200
        listing_id = listing.json()["listing_id"]
        buy_listing_headers = {**other_user, "Idempotency-Key": "bond-list-buy-1"}
        listing_buy = await client.post(
            f"/api/natbirzha/bonds/listings/{listing_id}/buy", headers=buy_listing_headers
        )
        listing_buy_replay = await client.post(
            f"/api/natbirzha/bonds/listings/{listing_id}/buy", headers=buy_listing_headers
        )
        assert listing_buy.status_code == 200 and listing_buy_replay.json() == listing_buy.json()
        assert listing_buy.json()["total_cost"] == 2200

    await engine.dispose()
    print("NATBIRZHA P2 HTTP security and idempotency checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
