"""Fixed simple-interest state credit remains Treasury-backed and idempotent."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import Depends, FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models as nat_models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.api import state_credit_routes
from backend.natbirzha.config import game_dt_iso
from backend.natbirzha.migrations import MIGRATIONS, run_natbirzha_migrations
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.state_credit_service import StateCreditService


def test_state_credit_uses_fixed_simple_interest_and_defaults_once() -> None:
    async def run() -> None:
        assert hasattr(nat_models, "NatStateCreditLoan"), "State credit loan model is missing"
        from backend.natbirzha.services.state_credit_service import StateCreditService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        started = datetime(2026, 9, 1, 12, 0)
        async with sessions() as session:
            company = NatCompany(
                user_id=991901,
                name="State Credit Test",
                specialization="miner",
                cash=500,
            )
            treasury = NatStateTreasury(id=1, cash=1_000)
            session.add_all([company, treasury])
            await session.commit()

            issued = await StateCreditService.request(
                session, company, principal=400, term_days=10, now=started
            )
            assert issued["cash_received"] == 400
            assert issued["treasury_cash"] == 600
            assert issued["remaining_cash"] == 900
            assert issued["loan"]["total_due"] == 700
            assert issued["loan"]["remaining_debt"] == 700
            assert issued["loan"]["due_at"] == game_dt_iso(started + timedelta(days=10))

            # One status read applies the overdue state; later reads do not add interest.
            first_default = await StateCreditService.status(
                session, company, now=started + timedelta(days=10, seconds=1)
            )
            second_default = await StateCreditService.status(
                session, company, now=started + timedelta(days=12)
            )
            assert first_default["loans"][0]["status"] == "DEFAULTED"
            assert second_default["loans"][0]["status"] == "DEFAULTED"
            assert second_default["loans"][0]["remaining_debt"] == 700

            loan_id = issued["loan"]["id"]
            partial = await StateCreditService.repay(
                session, company, loan_id, amount=250, now=started + timedelta(days=12)
            )
            assert partial["paid"] == 250
            assert partial["loan"]["status"] == "DEFAULTED"
            assert partial["loan"]["remaining_debt"] == 450
            assert partial["treasury_cash"] == 850
            assert partial["remaining_cash"] == 650

            final = await StateCreditService.repay(
                session, company, loan_id, amount=450, now=started + timedelta(days=12)
            )
            assert final["loan"]["status"] == "PAID"
            assert final["loan"]["remaining_debt"] == 0
            assert final["treasury_cash"] == 1_300
            assert final["remaining_cash"] == 200

            try:
                await StateCreditService.repay(
                    session, company, loan_id, amount=450, now=started + timedelta(days=12)
                )
            except ValueError as exc:
                assert "closed" in str(exc).lower() or "paid" in str(exc).lower()
            else:
                raise AssertionError("A paid state credit loan must not be repayable twice")

            cash_before = company.cash
            treasury_before = treasury.cash
            try:
                await StateCreditService.request(
                    session,
                    company,
                    principal=1_000,
                    term_days=1 << 1023,
                    now=started,
                )
            except ValueError as exc:
                assert "repayment amount" in str(exc).lower()
            else:
                raise AssertionError("Non-finite repayment balances must be rejected")
            assert company.cash == cash_before
            assert treasury.cash == treasury_before

        await engine.dispose()

    asyncio.run(run())


def test_state_credit_api_is_separate_and_mutations_are_idempotent() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            user = User(tg_id=991902, full_name="State Credit API Player", role="student")
            session.add(user)
            await session.flush()
            company = NatCompany(
                user_id=user.id,
                name="State Credit API Corp",
                specialization="miner",
                cash=500,
            )
            session.add_all([company, NatStateTreasury(id=1, cash=1_000)])
            await session.commit()
            company_id = company.id

        app = FastAPI()
        app.include_router(natbirzha_router, prefix="/api")

        async def test_session():
            async with sessions() as session:
                yield session

        async def test_company(
            x_test_company: int = Header(..., alias="X-Test-Company"),
            session: AsyncSession = Depends(get_db_session),
        ) -> NatCompany:
            company = await session.scalar(select(NatCompany).where(NatCompany.id == x_test_company))
            if company is None:
                raise HTTPException(status_code=404, detail="Company not found")
            return company

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_current_company] = test_company
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"X-Test-Company": str(company_id)}
            status_path = "/api/natbirzha/finance/state-loans"
            issue_body = {"principal": 400, "term_days": 10}

            missing_key = await client.post(status_path, headers=headers, json=issue_body)
            assert missing_key.status_code == 400

            overdrawn = await client.post(
                status_path,
                headers={**headers, "Idempotency-Key": "state-credit-insufficient"},
                json={"principal": 1_001, "term_days": 10},
            )
            assert overdrawn.status_code == 400
            unchanged = await client.get(status_path, headers=headers)
            assert unchanged.status_code == 200
            assert unchanged.json()["treasury_cash"] == 1_000
            assert unchanged.json()["loans"] == []

            issued = await client.post(
                status_path,
                headers={**headers, "Idempotency-Key": "state-credit-issue"},
                json=issue_body,
            )
            replay = await client.post(
                status_path,
                headers={**headers, "Idempotency-Key": "state-credit-issue"},
                json=issue_body,
            )
            assert issued.status_code == 200, issued.text
            assert issued.json() == replay.json()
            issue_data = issued.json()
            assert issue_data["success"] is True
            assert issue_data["cash_received"] == 400
            assert issue_data["treasury_cash"] == 600
            assert issue_data["remaining_cash"] == 900
            assert issue_data["loan"]["total_due"] == 700

            status = await client.get(status_path, headers=headers)
            assert status.status_code == 200, status.text
            assert status.json()["treasury_cash"] == 600
            assert status.json()["interest_rate_pct"] == 7.5
            assert status.json()["loans"][0]["term_days"] == 10

            loan_id = issue_data["loan"]["id"]
            repay_path = f"{status_path}/{loan_id}/repay"
            repay_body = {"amount": 250}
            repaid = await client.post(
                repay_path,
                headers={**headers, "Idempotency-Key": "state-credit-repay"},
                json=repay_body,
            )
            repay_replay = await client.post(
                repay_path,
                headers={**headers, "Idempotency-Key": "state-credit-repay"},
                json=repay_body,
            )
            assert repaid.status_code == 200, repaid.text
            assert repaid.json() == repay_replay.json()
            assert repaid.json()["loan"]["remaining_debt"] == 450
            assert repaid.json()["treasury_cash"] == 850
            assert repaid.json()["remaining_cash"] == 650

            changed_payload = await client.post(
                repay_path,
                headers={**headers, "Idempotency-Key": "state-credit-repay"},
                json={"amount": 300},
            )
            assert changed_payload.status_code == 409

        async with sessions() as session:
            company = await session.get(NatCompany, company_id)
            treasury = await session.get(NatStateTreasury, 1)
            assert company.cash == 650
            assert treasury.cash == 850
        await engine.dispose()

    asyncio.run(run())


def test_state_credit_migration_is_registered_and_repeatable() -> None:
    versions = [version for version, _ in MIGRATIONS]
    assert "natbirzha_v5_001_state_credit" in versions

    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE nat_companies (id INTEGER PRIMARY KEY)"))
            await run_natbirzha_migrations(connection)
            await run_natbirzha_migrations(connection)
            tables = {
                row[0]
                for row in (await connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )).all()
            }
            applied = await connection.scalar(text(
                "SELECT COUNT(*) FROM nat_schema_versions WHERE version='natbirzha_v5_001_state_credit'"
            ))
        await engine.dispose()
        assert "nat_state_credit_loans" in tables
        assert applied == 1

    asyncio.run(run())


def test_repayment_replays_winner_if_same_key_closes_loan_concurrently(monkeypatch) -> None:
    async def run() -> None:
        winner = {
            "success": True,
            "paid": 700,
            "loan": {"id": 5, "status": "PAID", "remaining_debt": 0},
            "treasury_cash": 1_700,
            "remaining_cash": 300,
        }
        checks = 0

        class FakeSession:
            rollbacks = 0

            async def rollback(self):
                self.rollbacks += 1

        async def check_or_conflict(_cls, _session, _user, _endpoint, _key, _payload):
            nonlocal checks
            checks += 1
            return None if checks == 1 else (200, winner)

        async def lose_race(_cls, *_args, **_kwargs):
            raise ValueError("State credit loan is already closed")

        monkeypatch.setattr(
            IdempotencyService, "check_or_conflict", classmethod(check_or_conflict)
        )
        monkeypatch.setattr(StateCreditService, "repay", classmethod(lose_race))
        session = FakeSession()
        response = await state_credit_routes.repay_state_credit(
            loan_id=5,
            request=state_credit_routes.StateCreditRepaymentRequest(amount=700),
            idempotency_key="same-repayment-key",
            company=SimpleNamespace(id=9, user_id=11),
            session=session,
        )

        assert response == winner
        assert checks == 2
        assert session.rollbacks == 1

    asyncio.run(run())


def test_company_reset_removes_state_credit_records() -> None:
    async def run() -> None:
        from backend.natbirzha.services.state_credit_service import StateCreditService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            user = User(tg_id=991903, full_name="Reset Credit Player", role="student")
            session.add(user)
            await session.flush()
            company = NatCompany(
                user_id=user.id,
                name="Reset Credit Corp",
                specialization="miner",
                cash=100,
            )
            session.add_all([company, NatStateTreasury(id=1, cash=1_000)])
            await session.flush()
            await StateCreditService.request(
                session, company, principal=100, term_days=1, commit=False
            )
            await session.commit()
            assert await CompanyService.reset_company_for_user(
                session, user.id, commit=True
            )
            count = await session.scalar(select(func.count()).select_from(nat_models.NatStateCreditLoan))
            assert count == 0

        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", __file__]))
