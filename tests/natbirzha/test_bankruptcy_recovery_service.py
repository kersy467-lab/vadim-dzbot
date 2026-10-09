"""Loan write-off and restart behavior for a bankrupt company."""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from fastapi import FastAPI, Header, HTTPException
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.abspath("."))

from backend.db.models import Base, User
from backend.db.session import get_db_session
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.contracts import NatLoan
from backend.natbirzha.models.state_credit import NatStateCreditLoan
from backend.natbirzha.services.bankruptcy_recovery_service import BankruptcyRecoveryService
from backend.natbirzha.config import nat_settings


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions


def test_bankruptcy_forgives_open_loans_and_cancels_pending_credit() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        async with sessions() as session:
            company = NatCompany(user_id=992001, name="Debt Corp", specialization="mining", cash=0, is_bankrupt=True)
            session.add(company)
            await session.flush()
            current = datetime(2026, 10, 9, 12)
            loans = [
                NatLoan(company_id=company.id, principal=1000, remaining_debt=1200, due_date=date(2026, 10, 23), status="ACTIVE"),
                NatLoan(company_id=company.id, principal=500, remaining_debt=700, due_date=date(2026, 10, 1), status="DEFAULTED"),
                NatLoan(company_id=company.id, principal=300, remaining_debt=0, due_date=date(2026, 10, 1), status="PAID"),
            ]
            state_loans = [
                NatStateCreditLoan(company_id=company.id, principal=2000, total_due=2400, remaining_debt=2400, term_days=2, due_at=current + timedelta(days=2), status="ACTIVE"),
                NatStateCreditLoan(company_id=company.id, principal=1000, total_due=1200, remaining_debt=1300, term_days=2, due_at=current, status="DEFAULTED"),
                NatStateCreditLoan(company_id=company.id, principal=800, total_due=900, remaining_debt=900, term_days=2, due_at=current, status="PENDING"),
                NatStateCreditLoan(company_id=company.id, principal=600, total_due=700, remaining_debt=0, term_days=2, due_at=current, status="REJECTED"),
            ]
            session.add_all([*loans, *state_loans])
            await session.flush()

            result = await BankruptcyRecoveryService.forgive_open_loans(session, company.id)

            assert result["loans_forgiven"] == 4
            assert result["pending_cancelled"] == 1
            assert result["debt_written_off"] == 5600
            assert [(loan.status, loan.remaining_debt) for loan in loans] == [
                ("FORGIVEN", 0), ("FORGIVEN", 0), ("PAID", 0),
            ]
            assert [(loan.status, loan.remaining_debt) for loan in state_loans] == [
                ("FORGIVEN", 0), ("FORGIVEN", 0), ("CANCELLED", 0), ("REJECTED", 0),
            ]

            repeated = await BankruptcyRecoveryService.forgive_open_loans(session, company.id)
            assert repeated["loans_forgiven"] == 0
            assert repeated["debt_written_off"] == 0
        await engine.dispose()

    asyncio.run(check())


def test_bankruptcy_restart_recreates_company_with_cash_bonus() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        async with sessions() as session:
            user = User(tg_id=992002, full_name="Restart Player", role="student", is_tester=False)
            session.add(user)
            await session.flush()
            company = NatCompany(
                user_id=user.id, name="Restart Corp", specialization="mining", custom_ticker="RSTR",
                level=12, cash=0, pvc_balance=17, nat_balance=17, is_bankrupt=True,
            )
            session.add(company)
            await session.commit()
            old_id = company.id
            starting_cash = float(nat_settings.STARTING_CASH)

        async with sessions() as session:
            old_company = await session.get(NatCompany, old_id)
            restarted = await BankruptcyRecoveryService.restart_company(session, old_company, commit=True)
            assert restarted.name == "Restart Corp"
            assert restarted.specialization == "miner"
            assert restarted.level == 1
            assert restarted.cash == starting_cash + 100_000
            assert restarted.is_bankrupt is False
            assert restarted.pvc_balance == restarted.nat_balance == 17
            assert await session.scalar(
                select(NatCompany.id).where(NatCompany.user_id == user.id)
            ) == restarted.id
        await engine.dispose()

    asyncio.run(check())


def test_solvent_company_cannot_claim_bankruptcy_restart_grant() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        async with sessions() as session:
            user = User(tg_id=992003, full_name="Solvent Player", role="student", is_tester=False)
            session.add(user)
            await session.flush()
            company = NatCompany(user_id=user.id, name="Solvent Corp", specialization="mining", cash=50_000)
            session.add(company)
            await session.commit()
            try:
                await BankruptcyRecoveryService.restart_company(session, company, commit=False)
                assert False, "solvent company must not receive the bankruptcy grant"
            except ValueError as exc:
                assert "банкрот" in str(exc).lower()
        await engine.dispose()

    asyncio.run(check())


def test_bankruptcy_restart_api_shows_liquidation_and_restarts_company() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        async with sessions() as session:
            user = User(tg_id=992004, full_name="Bankrupt Player", role="student", is_tester=True)
            session.add(user)
            await session.flush()
            company = NatCompany(
                user_id=user.id, name="Liquidated Corp", specialization="mining", cash=0, is_bankrupt=True,
            )
            session.add(company)
            await session.commit()
            user_id = user.id

        app = FastAPI()
        app.include_router(natbirzha_router, prefix="/api")

        async def test_session():
            async with sessions() as session:
                yield session

        async def test_user(x_test_user: int | None = Header(None, alias="X-Test-User")) -> User:
            if x_test_user is None:
                raise HTTPException(status_code=401, detail="Missing test identity")
            async with sessions() as session:
                user = await session.get(User, x_test_user)
                if user is None:
                    raise HTTPException(status_code=401, detail="Unknown test identity")
                return user

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_strict_natbirzha_user] = test_user
        headers = {"X-Test-User": str(user_id), "Idempotency-Key": "bankruptcy-restart-api"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            status = await client.get("/api/natbirzha/bankruptcy/status", headers=headers)
            assert status.status_code == 200, status.text
            assert status.json()["status"] == "BANKRUPT"
            assert status.json()["assets_liquidated"] is True

            restarted = await client.post("/api/natbirzha/bankruptcy/restart", headers=headers)
            assert restarted.status_code == 200, restarted.text
            data = restarted.json()
            assert data["success"] is True
            assert data["cash_grant"] == 100_000
            assert data["company"]["cash"] == nat_settings.STARTING_CASH + 100_000
            assert data["company"]["name"] == "Liquidated Corp"

            status = await client.get("/api/natbirzha/bankruptcy/status", headers=headers)
            assert status.status_code == 200
            assert status.json()["is_bankrupt"] is False
        await engine.dispose()

    asyncio.run(check())
