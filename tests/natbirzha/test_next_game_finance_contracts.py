import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameLedger
from backend.natbirzha.services.next_game_finance_service import NextGameFinanceContractService
from backend.natbirzha.services.next_game_service import NextGameService


def test_direct_finance_contract_escrows_accepts_repay_and_conserves_cash():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 10, 10, 12)
        async with sessions() as session:
            await NextGameService.create_company(session, 840_001, "Lender")
            await NextGameService.create_company(session, 840_002, "Borrower")
            lender = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 840_001
            ))
            borrower = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 840_002
            ))
            lender_id, borrower_id = lender.id, borrower.id
            lender_cash = float(lender.cash)
            borrower_cash = float(borrower.cash)

            offer = await NextGameFinanceContractService.create_offer(
                session, 840_001, borrower_id, 10_000, 100, 5,
                idempotency_key="direct-offer-1", now=now,
            )
            assert offer["contract"]["status"] == "OPEN"
            assert float(lender.cash) == lender_cash - 10_000
            assert float(borrower.cash) == borrower_cash
            replay = await NextGameFinanceContractService.create_offer(
                session, 840_001, borrower_id, 10_000, 100, 5,
                idempotency_key="direct-offer-1", now=now,
            )
            assert replay == offer

            accepted = await NextGameFinanceContractService.accept_offer(
                session, 840_002, offer["contract"]["id"],
                idempotency_key="direct-accept-1", now=now,
            )
            assert accepted["contract"]["status"] == "ACTIVE"
            assert float(borrower.cash) == borrower_cash + 10_000
            with pytest.raises(ValueError, match="активный займ"):
                await NextGameFinanceContractService.accept_offer(
                    session, 840_002, offer["contract"]["id"],
                    idempotency_key="direct-accept-2", now=now,
                )

            repaid = await NextGameFinanceContractService.repay_loan(
                session, 840_002, offer["contract"]["id"],
                idempotency_key="direct-repay-1", now=now + timedelta(days=3),
            )
            assert repaid["paid_amount"] == 10_300
            assert float(borrower.cash) == borrower_cash - 300
            assert float(lender.cash) == lender_cash + 300
            ledger = list((await session.scalars(
                select(NatNextGameLedger).where(
                    NatNextGameLedger.action.in_((
                        "DIRECT_LOAN_ESCROW", "DIRECT_LOAN_DISBURSED", "DIRECT_LOAN_REPAY",
                    ))
                ).order_by(NatNextGameLedger.id)
            )).all())
            assert len(ledger) == 4
            assert all(abs(row.cash_company_delta + row.cash_treasury_delta) < 0.01 for row in ledger)

        await engine.dispose()

    asyncio.run(check())


def test_direct_finance_offer_can_be_cancelled_once_and_refunds_lender():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            await NextGameService.create_company(session, 840_011, "Offer lender")
            await NextGameService.create_company(session, 840_012, "Offer target")
            lender = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 840_011
            ))
            target = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 840_012
            ))
            cash_before = float(lender.cash)
            offer = await NextGameFinanceContractService.create_offer(
                session, 840_011, target.id, 1_000, 25, 2,
                idempotency_key="direct-cancel-offer", now=datetime(2026, 10, 10),
            )
            cancelled = await NextGameFinanceContractService.cancel_offer(
                session, 840_011, offer["contract"]["id"],
                idempotency_key="direct-cancel-1",
            )
            assert cancelled["contract"]["status"] == "CANCELLED"
            assert float(lender.cash) == cash_before
            replay = await NextGameFinanceContractService.cancel_offer(
                session, 840_011, offer["contract"]["id"],
                idempotency_key="direct-cancel-1",
            )
            assert replay == cancelled

        await engine.dispose()

    asyncio.run(check())
