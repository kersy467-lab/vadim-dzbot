import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_banking import NatNextGameBankPayment
from backend.natbirzha.services.next_game_banking_service import NextGameBankingService
from backend.natbirzha.services.next_game_service import NextGameService


def test_bank_accounts_enable_fee_charging_company_payments_once():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            await NextGameService.create_company(session, 810_001, "Банк")
            await NextGameService.select_sector(session, 810_001, "bank")
            await NextGameService.select_branch(session, 810_001, "retail")
            await NextGameService.build_facility(session, 810_001)
            bank = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 810_001
            ))
            await NextGameService.create_company(session, 810_002, "Поставщик")
            await NextGameService.create_company(session, 810_003, "Покупатель")
            supplier = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 810_002
            ))
            buyer = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 810_003
            ))
            bank_id = bank.id
            supplier_id, buyer_id = supplier.id, buyer.id
            before = (float(bank.cash), float(supplier.cash), float(buyer.cash))

            await NextGameBankingService.open_account(session, 810_002, bank_id)
            await NextGameBankingService.open_account(session, 810_003, bank_id)
            payment = await NextGameBankingService.transfer(
                session, 810_003, bank_id, supplier_id, 1_000,
                idempotency_key="supplier-invoice-1",
            )
            assert payment["payment"]["amount"] == 1_000
            assert payment["payment"]["fee"] == 10

            replay = await NextGameBankingService.transfer(
                session, 810_003, bank_id, supplier_id, 1_000,
                idempotency_key="supplier-invoice-1",
            )
            assert replay == payment
            await session.commit()

            await session.refresh(bank)
            await session.refresh(supplier)
            await session.refresh(buyer)
            assert round(float(bank.cash) - before[0], 2) == 10
            assert round(float(supplier.cash) - before[1], 2) == 1_000
            assert round(before[2] - float(buyer.cash), 2) == 1_010
            records = list((await session.scalars(select(NatNextGameBankPayment))).all())
            assert len(records) == 1
            bank_snapshot = await NextGameService.snapshot(session, 810_001)
            assert bank_snapshot["banking"]["bank_summary"] == {
                "customer_accounts": 2,
                "fee_income": 10,
                "loan_interest_income": 0,
                "loans_outstanding": 0,
            }
            buyer_snapshot = await NextGameService.snapshot(session, 810_003)
            assert buyer_snapshot["banking"]["accounts"][0]["bank_name"] == "Банк"
            assert buyer_snapshot["banking"]["payments"][0]["amount"] == 1_000

        await engine.dispose()

    asyncio.run(check())


def test_payment_requires_two_accounts_and_sufficient_cash():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            await NextGameService.create_company(session, 820_001, "Банк тест")
            await NextGameService.select_sector(session, 820_001, "bank")
            await NextGameService.select_branch(session, 820_001, "retail")
            await NextGameService.build_facility(session, 820_001)
            bank = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 820_001
            ))
            await NextGameService.create_company(session, 820_002, "Без счёта")
            await NextGameService.create_company(session, 820_003, "Получатель")
            await NextGameService.create_company(session, 820_004, "Плательщик")
            receiver = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 820_003
            ))
            payer = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 820_004
            ))
            payer.cash = 1_000
            await NextGameBankingService.open_account(session, 820_003, bank.id)
            await NextGameBankingService.open_account(session, 820_004, bank.id)
            with pytest.raises(ValueError, match="расчётный счёт"):
                await NextGameBankingService.transfer(
                    session, 820_002, bank.id, receiver.id, 100,
                    idempotency_key="missing-account",
                )

            with pytest.raises(ValueError, match="Недостаточно cash"):
                await NextGameBankingService.transfer(
                    session, 820_004, bank.id, receiver.id, 10_000,
                    idempotency_key="self-pay",
                )

        await engine.dispose()

    asyncio.run(check())
