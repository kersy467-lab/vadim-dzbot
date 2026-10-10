import asyncio
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_equity import (
    NatNextGameShareHolding, NatNextGameShareOrder, NatNextGameShareTrade,
)
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_equity_service import NextGameEquityService


def test_ipo_trade_dividend_and_market_price_guard_are_company_scoped():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 551801, "Завод для IPO")
            await NextGameService.select_sector(session, 551801, "technology")
            await NextGameService.select_branch(session, 551801, "electronics")
            await NextGameService.build_facility(session, 551801, now=now)
            issuer = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 551801
            ))
            issuer.level = 5
            await NextGameService.create_company(session, 551802, "Первый инвестор")
            await NextGameService.create_company(session, 551803, "Второй инвестор")
            await session.commit()

            ipo = await NextGameEquityService.open_ipo(session, 551801, now=now)
            ipo_id = ipo["issue"]["id"]
            initial_price = ipo["issue"]["initial_price"]
            assert ipo["issue"]["float_shares"] == 10_000

            with pytest.raises(ValueError, match="собственные акции"):
                await NextGameEquityService.create_order(
                    session, 551801, ipo_id, "BUY", 1, initial_price, now=now
                )

            bought = await NextGameEquityService.create_order(
                session, 551802, ipo_id, "BUY", 100, initial_price, now=now
            )
            assert bought["executed_shares"] == 100
            assert bought["trades"][0]["buyer_company_name"] == "Первый инвестор"
            holding = await session.scalar(select(NatNextGameShareHolding).where(
                NatNextGameShareHolding.company_id != issuer.id,
                NatNextGameShareHolding.shares > 0,
            ))
            assert holding is not None and holding.shares == 100

            dividend = await NextGameEquityService.distribute_dividend(
                session, 551801, 0.5, now=now
            )
            assert dividend["total_paid"] == 50
            payment = dividend["payments"][0]
            assert payment["company_name"] == "Первый инвестор"
            assert payment["shares"] == 100
            assert payment["amount"] == 50
            investor_snapshot = await NextGameService.snapshot(session, 551802, now=now)
            assert investor_snapshot["equity"]["positions"][0]["dividends_received"] == 50

            ipo_ask = await session.scalar(select(NatNextGameShareOrder).where(
                NatNextGameShareOrder.issue_id == ipo_id,
                NatNextGameShareOrder.company_id == issuer.id,
                NatNextGameShareOrder.status == "OPEN",
            ))
            await NextGameEquityService.cancel_order(session, 551801, ipo_ask.id)
            seller = await NextGameEquityService.create_order(
                session, 551802, ipo_id, "SELL", 20, initial_price * 1.5, now=now
            )
            buyer = await NextGameEquityService.create_order(
                session, 551803, ipo_id, "BUY", 20, initial_price * 1.5, now=now
            )
            assert seller["executed_shares"] == 0
            assert buyer["executed_shares"] == 0
            cancelled_high_bid = await NextGameEquityService.cancel_order(
                session, 551803, buyer["order"]["id"],
            )
            assert cancelled_high_bid["released_cash"] == round(20 * initial_price * 1.5, 8)
            investor_two = await session.scalar(select(NatNextGameCompany).where(
                NatNextGameCompany.owner_tg_id == 551803
            ))
            cash_before_low_bid = float(investor_two.cash)
            low_bid = await NextGameEquityService.create_order(
                session, 551803, ipo_id, "BUY", 20, initial_price * 0.5, now=now
            )
            assert low_bid["executed_shares"] == 0
            assert float(investor_two.cash) == cash_before_low_bid - round(20 * initial_price * 0.5, 8)
            cancelled_low_bid = await NextGameEquityService.cancel_order(
                session, 551803, low_bid["order"]["id"],
            )
            assert cancelled_low_bid["released_cash"] == round(20 * initial_price * 0.5, 8)
            assert float(investor_two.cash) == cash_before_low_bid
            assert await session.scalar(select(NatNextGameShareTrade).where(
                NatNextGameShareTrade.price > initial_price * 1.15
            )) is None

        await engine.dispose()

    asyncio.run(check())
