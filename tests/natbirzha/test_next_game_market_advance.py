import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401

from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameTreasury
from backend.natbirzha.models.next_game_advance import NatNextGameMarketAdvance
from backend.natbirzha.services.next_game_advance_service import NextGameAdvanceService
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import NextGameService


async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions


async def anchor(session):
    # Real matched orders: three executions, two independent counterparty pairs.
    for owner in (95201, 95202, 95203):
        await NextGameService.create_company(session, owner, f"Участник {owner}")
    await NextGameService.trade(session, 95201, "energy", "BUY", 500)
    for buyer in (95202, 95203):
        await NextGameMarketService.create_limit_order(session, 95201, "energy", "SELL", 250, 8)
        await NextGameMarketService.create_limit_order(session, buyer, "energy", "BUY", 250, 8)
    await NextGameMarketService.create_limit_order(session, 95202, "energy", "SELL", 250, 8)
    await NextGameMarketService.create_limit_order(session, 95203, "energy", "BUY", 250, 8)


def test_advance_locks_order_and_repaid_fills_do_not_double_pay_seller():
    async def check():
        engine, sessions = await database()
        async with sessions() as session:
            await anchor(session)
            await NextGameService.create_company(session, 95301, "Финансируемый продавец")
            await NextGameService.create_company(session, 95302, "Новый покупатель")
            await NextGameService.trade(session, 95301, "energy", "BUY", 20)
            company = await NextGameService._owned_company(session, 95301)
            treasury = await session.get(NatNextGameTreasury, 1)
            before_cash, before_treasury = company.cash, treasury.cash
            sell = await NextGameMarketService.create_limit_order(session, 95301, "energy", "SELL", 10, 8)
            assert sell["order"]["advance_paid"] == 80
            assert sell["order"]["advance_locked"]
            assert company.cash == before_cash + 80
            assert treasury.cash == before_treasury - 80
            with pytest.raises(ValueError, match="профинансировала"):
                await NextGameMarketService.cancel_order(session, 95301, sell["order"]["id"])
            await NextGameMarketService.create_limit_order(session, 95302, "energy", "BUY", 4, 8)
            funding = await session.get(NatNextGameMarketAdvance, sell["order"]["id"])
            assert funding.outstanding_amount == 48
            assert company.cash == before_cash + 80
            assert treasury.cash == before_treasury - 48
            await NextGameMarketService.create_limit_order(session, 95302, "energy", "BUY", 6, 8)
            assert funding.outstanding_amount == 0
            assert treasury.cash == before_treasury
            assert company.cash == before_cash + 80
        await engine.dispose()
    asyncio.run(check())


def test_no_history_self_print_and_high_limit_do_not_finance():
    async def check():
        engine, sessions = await database()
        async with sessions() as session:
            await NextGameService.create_company(session, 95401, "Самоторговля")
            await NextGameService.trade(session, 95401, "energy", "BUY", 100)
            own_bid = await NextGameMarketService.create_limit_order(session, 95401, "energy", "BUY", 1, 1000)
            own = await NextGameMarketService.create_limit_order(session, 95401, "energy", "SELL", 10, 8)
            assert own["trades"] == [] and own["order"]["advance_paid"] == 0
            assert await NextGameAdvanceService.reference(session, "energy") is None
            await NextGameMarketService.cancel_order(session, 95401, own_bid["order"]["id"])
            await NextGameMarketService.cancel_order(session, 95401, own["order"]["id"])
            await anchor(session)
            high = await NextGameMarketService.create_limit_order(session, 95401, "energy", "SELL", 10, 9)
            assert high["order"]["advance_paid"] == 0
            assert await NextGameAdvanceService.reference(session, "energy", high["order"]["company_id"]) == 8
        await engine.dispose()
    asyncio.run(check())


def test_advance_funds_only_unmatched_tail_and_total_exposure_is_bounded():
    async def check():
        engine, sessions = await database()
        async with sessions() as session:
            await anchor(session)
            await NextGameService.create_company(session, 95501, "Продавец")
            await NextGameService.create_company(session, 95502, "Покупатель")
            company = await NextGameService._owned_company(session, 95501)
            company.cash = 500_000
            await NextGameService.trade(session, 95501, "energy", "BUY", 9000)
            await NextGameMarketService.create_limit_order(session, 95502, "energy", "BUY", 2, 8)
            sell = await NextGameMarketService.create_limit_order(session, 95501, "energy", "SELL", 10, 8)
            assert sell["executed_quantity"] == 2
            assert sell["order"]["advance_paid"] == 64
            await NextGameMarketService.create_limit_order(session, 95501, "energy", "SELL", 5000, 8)
            second = await NextGameMarketService.create_limit_order(session, 95501, "energy", "SELL", 100, 8)
            assert second["order"]["advance_paid"] == 0
            total = await session.scalar(select(func.sum(NatNextGameMarketAdvance.outstanding_amount)).where(
                NatNextGameMarketAdvance.company_id == company.id,
            ))
            assert total == 30000
        await engine.dispose()
    asyncio.run(check())
