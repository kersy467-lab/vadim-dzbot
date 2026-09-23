"""State-share operation key conflicts use the API's 409 contract."""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api.state_share_routes import (
    StateShareTradeRequest,
    buy_state_shares,
)
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.services.state_share_service import StateShareService


def test_same_api_key_with_different_operation_payload_returns_409() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=932102,
                name="Share conflict company",
                specialization="miner",
                cash=100,
            )
            session.add_all([company, NatStateTreasury(id=1, cash=100)])
            await session.flush()
            issue = await StateShareService.issue(
                session,
                actor_id=777,
                title="Conflict test issue",
                purpose="same key, different quantity",
                volume=10,
                issue_price=1,
                projected_annual_profit=100,
                dividend_rate_pct=10,
                operation_key="conflict:issue",
                commit=False,
            )
            key = "same-key-different-payload"
            operation_key = f"api:state-share:buy:{company.id}:{issue['share_id']}:{key}"
            await StateShareService.buy(
                session, company, issue["share_id"], 2,
                operation_key=operation_key, commit=False,
            )

            with pytest.raises(HTTPException) as error:
                await buy_state_shares(
                    issue["share_id"],
                    StateShareTradeRequest(quantity=3),
                    idempotency_key=key,
                    company=company,
                    session=session,
                )
            assert error.value.status_code == 409
            assert company.cash == 98

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_same_api_key_with_different_operation_payload_returns_409()
    print("NATBIRZHA state share API conflict checks: PASS")
