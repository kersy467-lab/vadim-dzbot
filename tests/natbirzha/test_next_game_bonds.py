import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameTreasury
from backend.natbirzha.models.next_game_bonds import NatNextGameBondHolding, NatNextGameBondListing
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_bond_service import NextGameBondService
from backend.natbirzha.services.next_game_bond_accounting import required_liability, forfeit_company_holdings


async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions


async def cash_total(session):
    total = await session.scalar(select(func.sum(NatNextGameCompany.cash)))
    treasury = await session.get(NatNextGameTreasury, 1)
    return total + treasury.cash


def test_hourly_automatic_income_maturity_exact_and_no_duplicate_payment():
    async def check():
        engine, sessions = await database()
        start = datetime(2026, 10, 10, 12, 17, 3)
        async with sessions() as session:
            await NextGameService.create_company(session, 96201, "Инвестор")
            before = await cash_total(session)
            bought = await NextGameBondService.buy(session, 96201, 1, 10, now=start)
            company = await NextGameService._owned_company(session, 96201)
            assert company.cash == 9000
            assert await required_liability(session) == 1007
            holding = await session.get(NatNextGameBondHolding, bought["holding_id"])
            for hour in range(1, 169):
                await NextGameBondService.settle_all(session, now=start + timedelta(hours=hour))
            assert holding.coupon_paid == 7
            assert company.cash == pytest.approx(10007)
            assert holding.status == "MATURED"
            assert await required_liability(session) == 0
            await NextGameBondService.settle_all(session, now=start + timedelta(days=8))
            assert company.cash == pytest.approx(10007)
            assert await cash_total(session) == pytest.approx(before)
        await engine.dispose()
    asyncio.run(check())


def test_secondary_transfer_settles_old_owner_and_preserves_maturity_and_cash():
    async def check():
        engine, sessions = await database()
        start = datetime(2026, 10, 10)
        async with sessions() as session:
            await NextGameService.create_company(session, 96301, "Продавец")
            await NextGameService.create_company(session, 96302, "Покупатель")
            total = await cash_total(session)
            bought = await NextGameBondService.buy(session, 96301, 1, 10, now=start)
            listing = await NextGameBondService.list(session, 96301, bought["holding_id"], 4, 110, now=start)
            with pytest.raises(ValueError, match="собственные"):
                await NextGameBondService.buy_listing(session, 96301, listing["listing_id"], 1, now=start)
            transfer_at = start + timedelta(hours=2, minutes=30)
            transferred = await NextGameBondService.buy_listing(session, 96302, listing["listing_id"], 2, now=transfer_at)
            original = await session.get(NatNextGameBondHolding, bought["holding_id"])
            new = await session.get(NatNextGameBondHolding, transferred["holding_id"])
            assert original.units == 8 and new.units == 2
            assert new.matures_at == start + timedelta(days=7)
            seller = await NextGameService._owned_company(session, 96301)
            buyer = await NextGameService._owned_company(session, 96302)
            assert seller.cash == pytest.approx(9220.10)
            assert buyer.cash == 9780
            await NextGameBondService.cancel_listing(session, 96301, listing["listing_id"], now=transfer_at)
            await NextGameBondService.settle_all(session, now=start + timedelta(days=7))
            assert seller.cash == pytest.approx(10025.62)
            assert buyer.cash == pytest.approx(9981.38)
            assert await cash_total(session) == pytest.approx(total)
        await engine.dispose()
    asyncio.run(check())


def test_secondary_escrow_oversell_and_forfeited_assets_never_pay():
    async def check():
        engine, sessions = await database()
        start = datetime(2026, 10, 10)
        async with sessions() as session:
            await NextGameService.create_company(session, 96401, "Перерождение")
            bought = await NextGameBondService.buy(session, 96401, 3, 10, now=start)
            await NextGameBondService.list(session, 96401, bought["holding_id"], 8, 100, now=start)
            with pytest.raises(ValueError, match="свободных"):
                await NextGameBondService.list(session, 96401, bought["holding_id"], 3, 100, now=start)
            company = await NextGameService._owned_company(session, 96401)
            before_cash = company.cash
            await forfeit_company_holdings(session, company.id)
            await NextGameBondService.settle_all(session, now=start + timedelta(days=40))
            assert company.cash == before_cash
            assert await required_liability(session) == 0
            listing = await session.scalar(select(NatNextGameBondListing))
            assert listing.status == "FORFEITED"
        await engine.dispose()
    asyncio.run(check())


def test_future_coupon_and_principal_are_secured_from_other_bank_spending():
    async def check():
        engine, sessions = await database()
        start = datetime(2026, 10, 10)
        async with sessions() as session:
            await NextGameService.create_company(session, 96501, "Первый инвестор")
            await NextGameService.create_company(session, 96502, "Второй инвестор")
            await NextGameBondService.buy(session, 96501, 1, 10, now=start)
            treasury = await session.get(NatNextGameTreasury, 1)
            treasury.cash = 1007.05
            await session.flush()
            assert await NextGameService._available_treasury_cash(session, treasury) == pytest.approx(.05)
            with pytest.raises(ValueError, match="обеспечения купонов"):
                await NextGameBondService.buy(session, 96502, 1, 1, now=start)
            treasury.cash = 1007.695
            await session.flush()
            assert await NextGameService._available_treasury_cash(session, treasury) == pytest.approx(.695)
            with pytest.raises(ValueError, match="обеспечения купонов"):
                await NextGameBondService.buy(session, 96502, 1, 1, now=start)
            await NextGameBondService.settle_all(session, now=start + timedelta(days=7))
            assert treasury.cash == pytest.approx(.695)
        await engine.dispose()
    asyncio.run(check())


def test_subcent_hourly_interest_survives_unrelated_npc_cash_rounding():
    async def check():
        engine, sessions = await database()
        start = datetime(2026, 10, 10)
        async with sessions() as session:
            await NextGameService.create_company(session, 96601, "Малый инвестор")
            bought = await NextGameBondService.buy(session, 96601, 1, 1, now=start)
            company = await NextGameService._owned_company(session, 96601)
            await NextGameBondService.settle_all(session, now=start + timedelta(hours=1))
            assert company.cash == 9900
            await NextGameService.trade(session, 96601, "energy", "BUY", 1, now=start + timedelta(hours=1))
            await NextGameBondService.settle_all(session, now=start + timedelta(hours=2))
            assert company.cash == pytest.approx(9888.01)
            await NextGameBondService.settle_all(session, now=start + timedelta(days=7))
            holding = await session.get(NatNextGameBondHolding, bought["holding_id"])
            assert holding.coupon_paid == .70
            assert company.cash == pytest.approx(9988.70)
        await engine.dispose()
    asyncio.run(check())


def test_repeated_transfers_cannot_multiply_reserve_coupon_promise():
    async def check():
        engine, sessions = await database()
        start = datetime(2026, 10, 10)
        async with sessions() as session:
            await NextGameService.create_company(session, 96701, "Первый трейдер")
            await NextGameService.create_company(session, 96702, "Второй трейдер")
            bought = await NextGameBondService.buy(session, 96701, 1, 1, now=start)
            owner, buyer, holding_id = 96701, 96702, bought["holding_id"]
            total = await cash_total(session)
            for step in range(1, 31):
                current = start + timedelta(minutes=72 * step)
                offer = await NextGameBondService.list(session, owner, holding_id, 1, 100, now=current)
                transfer = await NextGameBondService.buy_listing(session, buyer, offer["listing_id"], 1, now=current)
                owner, buyer, holding_id = buyer, owner, transfer["holding_id"]
            await NextGameBondService.settle_all(session, now=start + timedelta(days=7))
            all_paid = await session.scalar(select(func.sum(NatNextGameBondHolding.coupon_paid)))
            assert all_paid == pytest.approx(.70)
            assert await required_liability(session) == 0
            assert await cash_total(session) == pytest.approx(total)
        await engine.dispose()
    asyncio.run(check())
