"""Fixed simple-interest state credit remains Treasury-backed and idempotent."""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


from fastapi import Depends, FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

class _SimpleMonkeyPatch:
    def __init__(self):
        self._undo = []
    def setattr(self, target, name, value):
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)
    def undo(self):
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)


from backend.db.models import Base, User
import backend.natbirzha.models as nat_models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.api import state_credit_routes
from backend.natbirzha.api.creator_routes import get_current_creator
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
                session, company, principal=400, term_days=5, now=started
            )
            assert issued["cash_received"] == 0
            assert issued["treasury_cash"] == 1_000
            assert issued["remaining_cash"] == 500
            assert issued["loan"]["status"] == "PENDING"
            assert issued["loan"]["total_due"] == 550
            assert issued["loan"]["remaining_debt"] == 550
            assert issued["loan"]["due_at"] is None

            approved_at = started + timedelta(hours=3)
            approved = await StateCreditService.decide(
                session, issued["loan"]["id"], actor_id=777, approved=True, now=approved_at
            )
            assert approved["cash_received"] == 400
            assert approved["treasury_cash"] == 600
            assert approved["remaining_cash"] == 900
            assert approved["loan"]["status"] == "ACTIVE"
            assert approved["loan"]["total_due"] == 550
            assert approved["loan"]["due_at"] == game_dt_iso(approved_at + timedelta(days=5))

            # One status read applies the overdue state; later reads do not add interest.
            first_default = await StateCreditService.status(
                session, company, now=approved_at + timedelta(days=5, seconds=1)
            )
            second_default = await StateCreditService.status(
                session, company, now=approved_at + timedelta(days=7)
            )
            assert first_default["loans"][0]["status"] == "DEFAULTED"
            assert second_default["loans"][0]["status"] == "DEFAULTED"
            assert second_default["loans"][0]["remaining_debt"] == 550

            loan_id = issued["loan"]["id"]
            partial = await StateCreditService.repay(
                session, company, loan_id, amount=250, now=approved_at + timedelta(days=7)
            )
            assert partial["paid"] == 250
            assert partial["loan"]["status"] == "DEFAULTED"
            assert partial["loan"]["remaining_debt"] == 300
            assert partial["treasury_cash"] == 850
            assert partial["remaining_cash"] == 650

            final = await StateCreditService.repay(
                session, company, loan_id, amount=300, now=approved_at + timedelta(days=7)
            )
            assert final["loan"]["status"] == "PAID"
            assert final["loan"]["remaining_debt"] == 0
            assert final["treasury_cash"] == 1_150
            assert final["remaining_cash"] == 350

            try:
                await StateCreditService.repay(
                    session, company, loan_id, amount=300, now=approved_at + timedelta(days=7)
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
                    term_days=6,
                    now=started,
                )
            except ValueError as exc:
                assert "term" in str(exc).lower() or "5" in str(exc)
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
            admin = User(tg_id=991904, full_name="State Credit API Admin", role="admin")
            session.add_all([user, admin])
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

        async def test_creator() -> User:
            async with sessions() as session:
                admin = await session.scalar(select(User).where(User.tg_id == 991904))
                assert admin is not None
                return admin

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_current_company] = test_company
        app.dependency_overrides[get_current_creator] = test_creator
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"X-Test-Company": str(company_id)}
            status_path = "/api/natbirzha/finance/state-loans"
            issue_body = {"principal": 400, "term_days": 5}

            missing_key = await client.post(status_path, headers=headers, json=issue_body)
            assert missing_key.status_code == 400

            overdrawn = await client.post(
                status_path,
                headers={**headers, "Idempotency-Key": "state-credit-insufficient"},
                json={"principal": 1_001, "term_days": 5},
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
            assert issue_data["cash_received"] == 0
            assert issue_data["treasury_cash"] == 1_000
            assert issue_data["remaining_cash"] == 500
            assert issue_data["loan"]["status"] == "PENDING"
            assert issue_data["loan"]["total_due"] == 550

            status = await client.get(status_path, headers=headers)
            assert status.status_code == 200, status.text
            assert status.json()["treasury_cash"] == 1_000
            assert status.json()["interest_rate_pct"] == 7.5
            assert status.json()["loans"][0]["term_days"] == 5
            assert status.json()["loans"][0]["status"] == "PENDING"

            review_queue = await client.get("/api/natbirzha/creator/state-credits?status=PENDING")
            assert review_queue.status_code == 200, review_queue.text
            assert review_queue.json()["requests"][0]["company_name"] == "State Credit API Corp"
            assert review_queue.json()["requests"][0]["principal"] == 400

            loan_id = issue_data["loan"]["id"]
            decision = await client.post(
                f"/api/natbirzha/creator/state-credits/{loan_id}/decision",
                headers={"Idempotency-Key": "state-credit-approve"},
                json={"approved": True},
            )
            assert decision.status_code == 200, decision.text
            assert decision.json()["loan"]["status"] == "ACTIVE"
            assert decision.json()["cash_received"] == 400

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
            assert repaid.json()["loan"]["remaining_debt"] == 300
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
    assert "natbirzha_v5_002_state_credit_approval" in versions

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
            columns = {
                row[1]
                for row in (await connection.execute(
                    text("PRAGMA table_info(nat_state_credit_loans)")
                )).all()
            }
        await engine.dispose()
        assert "nat_state_credit_loans" in tables
        assert applied == 1
        assert {"reviewed_by", "reviewed_at"} <= columns

    asyncio.run(run())


def test_repayment_replays_winner_if_same_key_closes_loan_concurrently(monkeypatch=None) -> None:
    mp = monkeypatch or _SimpleMonkeyPatch()
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

        try:
            mp.setattr(
                IdempotencyService, "check_or_conflict", classmethod(check_or_conflict)
            )
            mp.setattr(StateCreditService, "repay", classmethod(lose_race))
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
        finally:
            if hasattr(mp, "undo"):
                mp.undo()

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
            requested = await StateCreditService.request(
                session, company, principal=100, term_days=1, commit=False
            )
            await StateCreditService.decide(
                session, requested["loan"]["id"], actor_id=777, approved=True, commit=False
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
    test_state_credit_uses_fixed_simple_interest_and_defaults_once()
    test_state_credit_api_is_separate_and_mutations_are_idempotent()
    test_state_credit_migration_is_registered_and_repeatable()
    test_repayment_replays_winner_if_same_key_closes_loan_concurrently()
    test_company_reset_removes_state_credit_records()
    print("NATBIRZHA state credit checks: PASS")

