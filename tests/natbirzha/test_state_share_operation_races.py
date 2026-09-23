"""A request that wins while another caller is waiting must be replayed."""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.state_shares import NatStateShare, NatStateShareOperation
from backend.natbirzha.services.state_share_service import StateShareService


@pytest.mark.parametrize("operation_type", ["ISSUE", "BUY", "SELL"])
def test_share_operation_replays_record_that_appears_after_initial_miss(
    operation_type: str, monkeypatch
) -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=932001,
                name=f"Race {operation_type} Company",
                specialization="miner",
                cash=1_000,
            )
            session.add_all([company, NatStateTreasury(id=1, cash=100)])
            await session.flush()
            issue = await StateShareService.issue(
                session,
                actor_id=777,
                title="Race Share Seed",
                purpose="race test",
                volume=20,
                issue_price=5,
                projected_annual_profit=3_650,
                dividend_rate_pct=10,
                operation_key="seed:issue",
                commit=False,
                now=datetime(2026, 9, 23, 12),
            )
            if operation_type == "SELL":
                await StateShareService.buy(
                    session, company, issue["share_id"], 4,
                    operation_key="seed:buy", commit=False,
                )
            await session.commit()
            company_id = company.id
            share_id = issue["share_id"]

        operation_key = f"race:{operation_type.lower()}"
        winner_response = {"success": True, "winner": operation_type, "share_id": share_id}
        injected = False
        original_replay = StateShareService._replay.__func__

        async def inject_winner(cls, session, key, kind, payload):
            nonlocal injected
            existing = await original_replay(cls, session, key, kind, payload)
            if key == operation_key and existing is None and not injected:
                injected = True
                session.add(NatStateShareOperation(
                    operation_key=key,
                    operation_type=kind,
                    request_hash=cls._payload_hash(payload),
                    response_json=winner_response,
                ))
                await session.flush()
                return None
            return existing

        monkeypatch.setattr(StateShareService, "_replay", classmethod(inject_winner))
        async with sessions() as session:
            company = await session.get(NatCompany, company_id)
            treasury = await session.get(NatStateTreasury, 1)
            before = (company.cash, treasury.cash)
            share = await session.get(NatStateShare, share_id)
            before_supply = share.remaining_volume
            try:
                if operation_type == "ISSUE":
                    result = await StateShareService.issue(
                        session,
                        actor_id=777,
                        title="Race Issue Loser",
                        purpose="race test",
                        volume=10,
                        issue_price=5,
                        projected_annual_profit=3_650,
                        dividend_rate_pct=10,
                        operation_key=operation_key,
                        commit=False,
                    )
                elif operation_type == "BUY":
                    result = await StateShareService.buy(
                        session, company, share_id, 3,
                        operation_key=operation_key, commit=False,
                    )
                else:
                    result = await StateShareService.sell(
                        session, company, share_id, 2,
                        operation_key=operation_key, commit=False,
                    )
                await session.commit()
            except IntegrityError:
                await session.rollback()
                result = None

        assert result == winner_response
        async with sessions() as session:
            company = await session.get(NatCompany, company_id)
            treasury = await session.get(NatStateTreasury, 1)
            share = await session.get(NatStateShare, share_id)
            assert (company.cash, treasury.cash) == before
            assert share.remaining_volume == before_supply
            if operation_type == "ISSUE":
                assert await session.scalar(select(func.count(NatStateShare.id))) == 1
        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
