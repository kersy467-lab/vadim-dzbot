import asyncio
from datetime import timedelta
import pytest
from sqlalchemy import select
from test_next_game_operations import database, cash_total
from backend.natbirzha.models.next_game import NatNextGameLedger
from backend.natbirzha.models.next_game_civic import NatNextGameCityOrder
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_service.common import _utcnow
from backend.natbirzha.services.next_game_civic_service import NextGameCivicService as Civic
from backend.natbirzha.services.next_game_civic_accounting import required_liability
from backend.natbirzha.services.next_game_npc_policy import remaining_buyback


def test_npc_cannot_profit_from_bulk_buy_then_subcent_sale_fragments():
    async def check():
        async with database() as (session, company, facility):
            initial = await cash_total(session)
            purchase = await Game.trade(session, 981001, "water", "BUY", .0192)
            assert purchase["total"] == .04608
            cash = company.cash
            for _ in range(6):
                with pytest.raises(ValueError, match="0,01"):
                    await Game.trade(session, 981001, "water", "SELL", .0032)
            assert company.cash == cash
            assert (await Game._inventory_row(session, company.id, "water")).quantity == .0192
            # Exactly one cent is valid and subcent precision remains in the cash balance.
            await Game._change_inventory(session, company.id, "wood_raw", .0005)
            result = await Game.trade(session, 981001, "wood_raw", "SELL", .0005)
            assert result["total"] == .01
            result = await Game.trade(session, 981001, "water", "SELL", .0063)
            assert result["total"] == .01008
            assert await cash_total(session) == pytest.approx(initial, rel=0, abs=1e-7)
    asyncio.run(check())


def test_city_fragments_cannot_overpay_or_eat_the_remaining_order_reserve():
    async def check():
        async with database() as (session, company, facility):
            now = _utcnow()
            order = NatNextGameCityOrder(item_id="water", unit_price=2.16, quantity=1,
                remaining_quantity=1, rotation_at=now, expires_at=now + timedelta(hours=1), status="OPEN")
            session.add(order)
            await Game._change_inventory(session, company.id, "water", 1)
            await session.flush()
            treasury = await Game._treasury(session)
            treasury.cash = 2.16
            before_cash = company.cash
            for _ in range(6):
                with pytest.raises(ValueError, match="0,01"):
                    await Civic.fulfill(session, 981001, order.id, .0024, now)
            assert company.cash == before_cash and order.remaining_quantity == 1
            for _ in range(6):
                result = await Civic.fulfill(session, 981001, order.id, .0047, now)
                assert result["cash_received"] == .010152
                assert treasury.cash == pytest.approx(await required_liability(session), abs=1e-8)
            assert company.cash == pytest.approx(before_cash + .060912, rel=0, abs=1e-7)
            assert order.remaining_quantity == .9718
    asyncio.run(check())


def test_npc_import_is_audited_and_utility_limit_is_per_item_per_game_day():
    async def check():
        async with database() as (session, company, facility):
            treasury = await Game._treasury(session)
            stock = dict(treasury.inventory_json)
            stock["water"] = 0
            treasury.inventory_json = stock
            before = await cash_total(session)
            await Game.trade(session, 981001, "water", "BUY", 2)
            imports = (await session.scalars(select(NatNextGameLedger).where(NatNextGameLedger.action == "NPC_IMPORT"))).all()
            assert len(imports) == 1 and imports[0].quantity_treasury_delta == 2
            assert treasury.inventory_json["water"] == 0
            assert await cash_total(session) == pytest.approx(before, rel=0, abs=1e-7)
            await Game._change_inventory(session, company.id, "energy", 100000)
            for quantity in (10000, 10000, 10000, 7500):
                await Game.trade(session, 981001, "energy", "SELL", quantity)
            assert await remaining_buyback(session, company.id, "energy") == 0
            assert await remaining_buyback(session, company.id, "water") == 300000
            with pytest.raises(ValueError, match="Остаток выкупа"):
                await Game.trade(session, 981001, "energy", "SELL", 1)
            assert await remaining_buyback(session, company.id, "steel") is None
    asyncio.run(check())
