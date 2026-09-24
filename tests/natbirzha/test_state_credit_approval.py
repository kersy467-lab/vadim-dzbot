"""Credit applications remain pending until an audited-cap decision is made."""

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.services.state_credit_service import StateCreditService


def test_credit_requests_obey_five_day_and_aggregate_half_nav_limit() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=810_001, name="Credit Limit Corp", specialization="miner",
                cash=100, territory_tiles=4,
            )
            treasury = NatStateTreasury(id=1, cash=100_000)
            session.add_all([company, treasury])
            await session.commit()
            now = datetime(2026, 9, 24, 12)

            first = await StateCreditService.request(
                session, company, principal=15_000, term_days=5, now=now
            )
            assert first["loan"]["status"] == "PENDING"
            assert company.cash == 100 and treasury.cash == 100_000

            try:
                await StateCreditService.request(
                    session, company, principal=5_051, term_days=1, now=now
                )
            except ValueError as exc:
                assert "50%" in str(exc) or "limit" in str(exc).lower()
            else:
                raise AssertionError("Active and pending principal must share the 50% NAV cap")

            try:
                await StateCreditService.request(
                    session, company, principal=100, term_days=6, now=now
                )
            except ValueError as exc:
                assert "5" in str(exc) or "term" in str(exc).lower()
            else:
                raise AssertionError("A state credit term must not exceed five days")

            rejected = await StateCreditService.decide(
                session, first["loan"]["id"], actor_id=77, approved=False, now=now
            )
            assert rejected["loan"]["status"] == "REJECTED"
            assert company.cash == 100 and treasury.cash == 100_000

            second = await StateCreditService.request(
                session, company, principal=20_000, term_days=1, now=now
            )
            assert second["loan"]["status"] == "PENDING"
            assert treasury.cash == 100_000

        await engine.dispose()

    asyncio.run(check())


def test_credit_approval_rechecks_nav_limit_and_starts_clock_on_approval() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=810_002, name="Rechecked Credit Corp", specialization="miner",
                cash=0, territory_tiles=4,
            )
            treasury = NatStateTreasury(id=1, cash=100_000)
            session.add_all([company, treasury])
            await session.commit()
            requested_at = datetime(2026, 9, 24, 12)
            pending = await StateCreditService.request(
                session, company, principal=15_000, term_days=5, now=requested_at
            )

            company.territory_tiles = 1
            try:
                await StateCreditService.decide(
                    session, pending["loan"]["id"], actor_id=77, approved=True,
                    now=datetime(2026, 9, 25, 18),
                )
            except ValueError as exc:
                assert "50%" in str(exc) or "limit" in str(exc).lower()
            else:
                raise AssertionError("Approval must re-check the current company NAV")
            await session.refresh(company)
            await session.refresh(treasury)
            assert company.cash == 0 and treasury.cash == 100_000

            company.territory_tiles = 4
            approved_at = datetime(2026, 9, 25, 18)
            approved = await StateCreditService.decide(
                session, pending["loan"]["id"], actor_id=77, approved=True, now=approved_at
            )
            assert approved["loan"]["status"] == "ACTIVE"
            assert approved["loan"]["due_at"].startswith("2026-09-30T18:00:00")
            assert treasury.cash == 85_000 and company.cash == 15_000

        await engine.dispose()

    asyncio.run(check())
