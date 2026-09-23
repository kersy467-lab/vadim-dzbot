"""Creator permissions, player trades, portfolio values and request idempotency."""

import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.services.auth_service import get_current_company, get_strict_natbirzha_user


def test_creator_issue_and_player_trade_endpoints_are_authorized_and_idempotent() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            creator = User(tg_id=931201, full_name="State Share Creator", role="admin")
            player = User(tg_id=931202, full_name="State Share Player", role="student")
            session.add_all([creator, player])
            await session.flush()
            creator_company = NatCompany(user_id=creator.id, name="Share State Issuer", specialization="miner", cash=10_000)
            player_company = NatCompany(user_id=player.id, name="Share State Buyer", specialization="forester", cash=1_000)
            session.add_all([creator_company, player_company])
            await session.flush()
            session.add(NatStateTreasury(id=1, cash=100))
            session.add(NatStock(
                company_id=creator_company.id, total_shares=100, founder_shares=60,
                float_shares=40, current_price=12.5, last_valuation=1250, is_listed=True,
            ))
            await session.flush()
            session.add(NatStockHolding(
                stock_id=1, holder_company_id=player_company.id,
                shares_count=2, avg_price=10,
            ))
            await session.commit()
            creator_id, player_id = creator.id, player.id
            player_company_id = player_company.id

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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            creator_headers = {"X-Test-User": str(creator_id)}
            player_headers = {"X-Test-User": str(player_id)}
            denied = await client.post(
                "/api/natbirzha/creator/shares/issue",
                headers={**player_headers, "Idempotency-Key": "forbidden-share"},
                json={"title": "Forbidden", "volume": 20, "issue_price": 5,
                      "projected_annual_profit": 1000, "dividend_rate_pct": 10},
            )
            assert denied.status_code == 403
            denied_creator_list = await client.get(
                "/api/natbirzha/creator/shares", headers=player_headers
            )
            assert denied_creator_list.status_code == 403

            issue_body = {
                "title": "State Infrastructure Shares",
                "purpose": "Roads and power grid",
                "volume": 20,
                "issue_price": 5,
                "projected_annual_profit": 3650,
                "dividend_rate_pct": 10,
            }
            invalid_issue = await client.post(
                "/api/natbirzha/creator/shares/issue",
                headers={**creator_headers, "Idempotency-Key": "invalid-share"},
                json={**issue_body, "volume": 0},
            )
            assert invalid_issue.status_code == 422
            missing_key = await client.post(
                "/api/natbirzha/creator/shares/issue", headers=creator_headers, json=issue_body
            )
            assert missing_key.status_code == 400
            creator_list = await client.get("/api/natbirzha/creator/shares", headers=creator_headers)
            assert creator_list.status_code == 200 and creator_list.json()["shares"] == []

            issue_headers = {**creator_headers, "Idempotency-Key": "issue-share-1"}
            issued = await client.post(
                "/api/natbirzha/creator/shares/issue", headers=issue_headers, json=issue_body
            )
            replay_issue = await client.post(
                "/api/natbirzha/creator/shares/issue", headers=issue_headers, json=issue_body
            )
            assert issued.status_code == 200 and issued.json() == replay_issue.json()
            share_id = issued.json()["share_id"]
            creator_list = await client.get("/api/natbirzha/creator/shares", headers=creator_headers)
            assert creator_list.json()["shares"][0]["purpose"] == "Roads and power grid"

            player_list = await client.get("/api/natbirzha/shares", headers=player_headers)
            assert player_list.status_code == 200
            assert player_list.json()["shares"][0]["remaining_volume"] == 20
            buy_headers = {**player_headers, "Idempotency-Key": "buy-share-1"}
            buy_body = {"quantity": 10}
            missing_trade_key = await client.post(
                f"/api/natbirzha/shares/{share_id}/buy", headers=player_headers, json=buy_body
            )
            assert missing_trade_key.status_code == 400
            bought = await client.post(
                f"/api/natbirzha/shares/{share_id}/buy", headers=buy_headers, json=buy_body
            )
            replay_buy = await client.post(
                f"/api/natbirzha/shares/{share_id}/buy", headers=buy_headers, json=buy_body
            )
            assert bought.status_code == 200 and bought.json() == replay_buy.json()
            assert bought.json()["total_cost"] == 50

            sell_headers = {**player_headers, "Idempotency-Key": "sell-share-1"}
            sell_body = {"quantity": 2}
            sold = await client.post(
                f"/api/natbirzha/shares/{share_id}/sell",
                headers=sell_headers,
                json=sell_body,
            )
            replay_sale = await client.post(
                f"/api/natbirzha/shares/{share_id}/sell",
                headers=sell_headers,
                json=sell_body,
            )
            assert sold.status_code == 200 and sold.json()["total_proceeds"] == 10
            assert sold.json() == replay_sale.json()
            player_list_after_sale = await client.get("/api/natbirzha/shares", headers=player_headers)
            assert player_list_after_sale.json()["shares"][0]["remaining_volume"] == 12

            async with sessions() as session:
                treasury = await session.get(NatStateTreasury, 1)
                treasury.cash = 0
                await session.commit()
            failed_sale = await client.post(
                f"/api/natbirzha/shares/{share_id}/sell",
                headers={**player_headers, "Idempotency-Key": "insolvent-share-sale"},
                json={"quantity": 1},
            )
            assert failed_sale.status_code == 400
            async with sessions() as session:
                player_company = await session.get(NatCompany, player_company_id)
                assert player_company.cash == 960

            portfolio = await client.get("/api/natbirzha/portfolio", headers=player_headers)
            assert portfolio.status_code == 200, portfolio.text
            data = portfolio.json()
            assert data["stocks"][0]["market_price"] == 12.5
            assert data["state_shares"][0]["shares_count"] == 8
            assert data["summary"]["state_shares_market_value"] == 40

        async with sessions() as session:
            player_company = await session.get(NatCompany, player_company_id)
            treasury = await session.get(NatStateTreasury, 1)
            assert player_company.cash == 960
            assert treasury.cash == 0
        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_creator_issue_and_player_trade_endpoints_are_authorized_and_idempotent()
    print("NATBIRZHA state share API checks: PASS")
