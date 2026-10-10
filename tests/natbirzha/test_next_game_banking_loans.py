import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_banking import NatNextGameCorporateLoan
from backend.natbirzha.services.next_game_banking_service import NextGameBankingService
from backend.natbirzha.services.next_game_service import NextGameService


def test_bank_business_loan_is_cash_backed_idempotent_and_repaid_to_the_lender():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        now = datetime(2026, 10, 10, 12)
        async with sessions() as session:
            await NextGameService.create_company(session, 830_001, "Business Bank")
            await NextGameService.select_sector(session, 830_001, "bank")
            await NextGameService.select_branch(session, 830_001, "corporate")
            await NextGameService.build_facility(session, 830_001, now=now)
            bank = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 830_001
            ))
            await NextGameService.create_company(session, 830_002, "Borrower")
            borrower = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 830_002
            ))
            # Capitalize lender explicitly: the new build price leaves only 3000.
            bank.cash = 5000
            bank_id, borrower_id = bank.id, borrower.id
            bank_cash_before = float(bank.cash)
            borrower_cash_before = float(borrower.cash)
            await NextGameBankingService.open_account(session, 830_002, bank_id)

            loan = await NextGameBankingService.request_business_loan(
                session, 830_002, bank_id, 2_000, 7,
                idempotency_key="loan-invoice-1", now=now,
            )
            assert loan["loan"]["principal"] == 2_000
            assert loan["loan"]["maturity_amount"] == 2_070
            assert loan["loan"]["daily_rate"] == 0.005
            replay = await NextGameBankingService.request_business_loan(
                session, 830_002, bank_id, 2_000, 7,
                idempotency_key="loan-invoice-1", now=now,
            )
            assert replay == loan
            assert round(float(bank.cash) - bank_cash_before, 2) == -2_000
            assert round(float(borrower.cash) - borrower_cash_before, 2) == 2_000
            with pytest.raises(ValueError, match="активный кредит"):
                await NextGameBankingService.request_business_loan(
                    session, 830_002, bank_id, 1_000, 7,
                    idempotency_key="loan-invoice-2", now=now,
                )

            repaid = await NextGameBankingService.repay_business_loan(
                session, 830_002, loan["loan"]["id"],
                idempotency_key="loan-repay-1", now=now + timedelta(days=7),
            )
            assert repaid["paid_amount"] == 2_070
            assert round(float(borrower.cash) - borrower_cash_before, 2) == -70
            assert round(float(bank.cash) - bank_cash_before, 2) == 70
            row = await session.get(NatNextGameCorporateLoan, loan["loan"]["id"])
            assert row.status == "PAID"

        await engine.dispose()

    asyncio.run(check())
