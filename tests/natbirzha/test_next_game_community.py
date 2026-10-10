import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base
import backend.natbirzha.models
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_community import NatNextGameHelpRequest
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_admin_service import NextGameAdminService
from backend.natbirzha.services.next_game_community_service import NextGameCommunityService, profile
from backend.natbirzha.services.next_game_market_service import NextGameMarketService


@asynccontextmanager
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await NextGameService.create_company(session, 800001, "Получатель")
        await NextGameService.create_company(session, 800002, "Спонсор")
        yield session
    await engine.dispose()


def test_aid_all_levels_caps_donation_and_conserves_company_cash():
    async def check():
        async with database() as session:
            recipient = await NextGameService._owned_company(session, 800001)
            recipient.level = 60
            donor = await NextGameService._owned_company(session, 800002)
            original = recipient.cash + donor.cash
            result = await NextGameCommunityService.create_request(session, 800001, None, 1200, "Оборотные средства")
            with pytest.raises(ValueError, match="самому себе"):
                await NextGameCommunityService.donate(session, 800001, result["request_id"], 100)
            received = await NextGameCommunityService.donate(session, 800002, result["request_id"], 3000)
            assert received == {"success": True, "transferred": 1200, "status": "COMPLETE"}
            assert recipient.cash + donor.cash == original
            assert recipient.cash == 11200 and donor.cash == 8800
            with pytest.raises(ValueError, match="закрыт"):
                await NextGameCommunityService.donate(session, 800002, result["request_id"], 100)
    asyncio.run(check())


def test_aid_cannot_spend_escrowed_goods_or_close_another_company_request():
    async def check():
        async with database() as session:
            await NextGameService.trade(session, 800002, "water", "BUY", 100)
            await NextGameMarketService.create_limit_order(session, 800002, "water", "SELL", 90, 2)
            request = await NextGameCommunityService.create_request(session, 800001, "water", 20, "Для производства")
            with pytest.raises(ValueError, match="свободного товара"):
                await NextGameCommunityService.donate(session, 800002, request["request_id"], 20)
            with pytest.raises(ValueError, match="Свой запрос"):
                await NextGameCommunityService.close_request(session, 800002, request["request_id"])
            donated = await NextGameCommunityService.donate(session, 800002, request["request_id"], 10)
            assert donated["transferred"] == 10
            row = await session.get(NatNextGameHelpRequest, request["request_id"])
            assert row.received == 10 and row.status == "OPEN"
    asyncio.run(check())


def test_admin_grant_uses_reserve_and_records_reason():
    async def check():
        async with database() as session:
            company = await NextGameService._owned_company(session, 800001)
            treasury = await NextGameService._treasury(session)
            original = treasury.cash + company.cash
            await NextGameAdminService.operate(session, 800002, "CASH_GRANT", company.id, 1000, None, "Компенсация")
            assert company.cash == 11000
            assert treasury.cash + company.cash == original
            data = await NextGameAdminService.snapshot(session)
            assert data["audit"][0]["details"]["note"] == "Компенсация"
            with pytest.raises(ValueError, match="свободных средств"):
                await NextGameAdminService.operate(session, 800002, "CASH_GRANT", company.id, 1e12, None, "Тест")
    asyncio.run(check())


def test_fractional_market_cash_is_preserved_by_aid_and_admin_operations():
    async def check():
        async with database() as session:
            await NextGameService.create_company(session, 800003, "Третья компания")
            seller = await NextGameService._owned_company(session, 800001)
            await NextGameService._change_inventory(session, seller.id, "water", 1)
            await NextGameMarketService.create_limit_order(session, 800001, "water", "SELL", 1, .0051)
            await NextGameMarketService.create_limit_order(session, 800002, "water", "BUY", 1, .0051)
            treasury = await NextGameService._treasury(session)
            async def total():
                companies = (await session.scalars(select(NatNextGameCompany))).all()
                return treasury.cash + sum(row.cash for row in companies)
            before = await total()
            request = await NextGameCommunityService.create_request(session, 800003, None, 1, "Тест")
            await NextGameCommunityService.donate(session, 800001, request["request_id"], 1)
            assert await total() == pytest.approx(before, rel=0, abs=1e-7)
            assert seller.cash == pytest.approx(9999.0051, rel=0, abs=1e-8)
            await NextGameAdminService.operate(session, 800002, "CASH_GRANT", seller.id, 1, None, "Тест точности")
            assert await total() == pytest.approx(before, rel=0, abs=1e-7)
            assert seller.cash == pytest.approx(10000.0051, rel=0, abs=1e-8)
    asyncio.run(check())


def test_auto_upgrade_stops_at_nine_and_never_repeats_within_minute():
    async def check():
        async with database() as session:
            await NextGameService.select_sector(session, 800001, "technology")
            await NextGameService.select_branch(session, 800001, "ai_compute")
            await NextGameService.build_facility(session, 800001)
            company = await NextGameService._owned_company(session, 800001)
            await NextGameAdminService.operate(session, 800002, "CASH_GRANT", company.id, 100000, None, "Тест прокачки")
            facility = await session.scalar(select(NatNextGameFacility).where(NatNextGameFacility.company_id == company.id))
            facility.level = 8
            company.level = 10
            settings = await profile(session, company.id)
            settings.auto_upgrade = True
            current = datetime(2026, 10, 10, 12)
            facility.next_cycle_at = current + timedelta(days=1)
            await NextGameService.settle_company(session, 800001, now=current)
            after = company.cash
            assert facility.level == 9
            await NextGameService.settle_company(session, 800001, now=current + timedelta(seconds=10))
            await NextGameService.settle_company(session, 800001, now=current + timedelta(minutes=2))
            assert facility.level == 9 and company.cash == after
    asyncio.run(check())
