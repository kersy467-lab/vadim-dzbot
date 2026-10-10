import asyncio
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base
import backend.natbirzha.models
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameTreasury, NatNextGameLedger, NatNextGameInventory, NatNextGameMarketTrade
from backend.natbirzha.models.next_game_civic import NatNextGameTaxAssessment, NatNextGameCityOrder
from backend.natbirzha.services.next_game_civic_accounting import assess_company, event_multiplier, required_liability
from backend.natbirzha.services.next_game_civic_service import NextGameCivicService as Civic


async def setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_tax_daily_cutoff_carry_excludes_financing_and_duplicate_assessment():
    async def run():
        engine, sessions = await setup()
        async with sessions() as session:
            begin = datetime(2026, 10, 1, 6)
            company = NatNextGameCompany(owner_tg_id=91, name="Tax", cash=1000.00123456, created_at=begin)
            session.add_all([company, NatNextGameTreasury(id=1, cash=1000000, inventory_json={})])
            await session.flush()
            def ledger(action, cash, time):
                return NatNextGameLedger(company_id=company.id, action=action, cash_company_delta=cash,
                    cash_treasury_delta=-cash, created_at=time)
            session.add_all([ledger("BUY", -200, begin), ledger("OPERATING_COST", -100, begin),
                ledger("STARTUP_CAPITAL", 10000, begin), ledger("LOAN_ISSUE", 9000, begin),
                ledger("BUILD", -500, begin), ledger("ADVANCE", 500, begin),
                ledger("SELL", 400, begin + timedelta(days=1)),
                ledger("CITY_SALE", 100, begin + timedelta(days=2))])
            await session.flush()
            await assess_company(session, company, begin + timedelta(days=1, seconds=-1))
            assert not (await session.scalars(select(NatNextGameTaxAssessment))).all()
            await assess_company(session, company, begin + timedelta(days=1))
            await assess_company(session, company, begin + timedelta(days=2))
            await assess_company(session, company, begin + timedelta(days=2))
            rows = (await session.scalars(select(NatNextGameTaxAssessment).order_by(NatNextGameTaxAssessment.id))).all()
            assert len(rows) == 2
            assert rows[0].operating_profit == -300 and rows[0].amount == 0
            assert rows[1].taxable_profit == 100 and rows[1].amount == 13
            first = await Civic.pay_tax(session, 91, rows[1].id)
            assert await Civic.pay_tax(session, 91, rows[1].id) == first
            assert company.cash == pytest.approx(987.00123456)
            assert len((await session.scalars(select(NatNextGameLedger).where(NatNextGameLedger.action == "TAX_PAYMENT"))).all()) == 1
        await engine.dispose()
    asyncio.run(run())


def test_real_market_trade_counts_actual_execution_and_distinct_company():
    async def run():
        engine, sessions = await setup()
        async with sessions() as session:
            begin = datetime(2026, 10, 1, 6)
            seller = NatNextGameCompany(owner_tg_id=92, name="Seller", cash=1000, created_at=begin)
            buyer = NatNextGameCompany(owner_tg_id=93, name="Buyer", cash=1000, created_at=begin)
            session.add_all([seller, buyer]); await session.flush()
            session.add(NatNextGameMarketTrade(buy_order_id=1, sell_order_id=2,
                buyer_company_id=buyer.id, seller_company_id=seller.id, item_id="coal", price=50,
                quantity=10, executed_at=begin))
            await session.flush()
            await assess_company(session, seller, begin + timedelta(days=1))
            account = await assess_company(session, buyer, begin + timedelta(days=1))
            rows = (await session.scalars(select(NatNextGameTaxAssessment))).all()
            assert sorted(r.operating_profit for r in rows) == [-500, 500]
            assert sum(r.amount for r in rows) == 65 and account.loss_carry == 500
        await engine.dispose()
    asyncio.run(run())


def test_city_partial_fulfillment_is_conserved_budget_rotates_once_and_events_expire():
    async def run():
        engine, sessions = await setup()
        async with sessions() as session:
            now = datetime(2026, 10, 1, 7)
            company = NatNextGameCompany(owner_tg_id=94, name="City", sector_id="bank", cash=1000.00001234, created_at=now)
            treasury = NatNextGameTreasury(id=1, cash=1000000, inventory_json={})
            session.add_all([company, treasury]); await session.flush()
            await Civic.rotate_orders(session, now)
            orders = (await session.scalars(select(NatNextGameCityOrder))).all()
            assert 1 <= len(orders) <= 8 and await required_liability(session) <= 10000
            await Civic.rotate_orders(session, now)
            assert len((await session.scalars(select(NatNextGameCityOrder))).all()) == len(orders)
            order = orders[0]
            session.add(NatNextGameInventory(company_id=company.id, item_id=order.item_id, quantity=2))
            await session.flush()
            result = await Civic.fulfill(session, 94, order.id, 1, now)
            assert treasury.cash + company.cash == pytest.approx(1001000.00001234)
            assert result["cash_received"] == order.unit_price
            assert treasury.inventory_json[order.item_id] == 1
            assert order.remaining_quantity == order.quantity - 1
            with pytest.raises(ValueError):
                await Civic.fulfill(session, 94, order.id, 3, now)
            await Civic.create_event(session, 94, "bank", 24, now)
            assert await event_multiplier(session, company, now) == 1.25
            assert await event_multiplier(session, company, now + timedelta(hours=24)) == 1
            with pytest.raises(ValueError):
                await Civic.create_event(session, 94, "bank", 25, now)
            await Civic.rotate_orders(session, now + timedelta(days=1))
            assert all(row.status == "EXPIRED" for row in orders)
        await engine.dispose()
    asyncio.run(run())


def test_city_and_event_command_replay_and_payload_conflict():
    async def run():
        from types import SimpleNamespace
        from fastapi import HTTPException
        from backend.natbirzha.api.next_game_mutation import mutate
        engine, sessions = await setup()
        async with sessions() as session:
            now = datetime(2026, 10, 1, 7)
            company = NatNextGameCompany(owner_tg_id=95, name="Replay", cash=1000, created_at=now)
            session.add_all([company, NatNextGameTreasury(id=1, cash=1000000, inventory_json={})])
            await session.flush()
            await Civic.rotate_orders(session, now)
            order = await session.scalar(select(NatNextGameCityOrder).order_by(NatNextGameCityOrder.id))
            session.add(NatNextGameInventory(company_id=company.id, item_id=order.item_id, quantity=5))
            await session.commit()
            order_id = order.id
            admin = SimpleNamespace(id=95, tg_id=95)
            endpoint = f"/civic/orders/{order_id}/fulfill"
            payload = {"quantity": 1}
            first = await mutate(session, admin, "delivery", endpoint, payload,
                lambda: Civic.fulfill(session, 95, order_id, 1, now))
            replay = await mutate(session, admin, "delivery", endpoint, payload,
                lambda: Civic.fulfill(session, 95, order_id, 1, now))
            assert replay == first
            assert len((await session.scalars(select(NatNextGameLedger).where(NatNextGameLedger.action == "CITY_SALE"))).all()) == 1
            with pytest.raises(HTTPException) as error:
                await mutate(session, admin, "delivery", endpoint, {"quantity": 2},
                    lambda: Civic.fulfill(session, 95, order_id, 2, now))
            assert error.value.status_code == 409
            first_event = await mutate(session, admin, "event", "/civic/events", {"hours": 6},
                lambda: Civic.create_event(session, 95, "bank", 6, now))
            assert await mutate(session, admin, "event", "/civic/events", {"hours": 6},
                lambda: Civic.create_event(session, 95, "bank", 6, now)) == first_event
        await engine.dispose()
    asyncio.run(run())


def test_rebirth_settles_partial_day_without_retaxing_history(monkeypatch):
    async def run():
        from backend.natbirzha.services import next_game_civic_accounting as accounting
        engine, sessions = await setup()
        async with sessions() as session:
            begin = datetime(2026, 10, 1, 6)
            now = begin + timedelta(hours=12)
            monkeypatch.setattr(accounting, "_utcnow", lambda: now)
            company = NatNextGameCompany(owner_tg_id=96, name="Rebirth", cash=1000, created_at=begin)
            session.add_all([company, NatNextGameTreasury(id=1, cash=1000000, inventory_json={})])
            await session.flush()
            session.add(NatNextGameLedger(company_id=company.id, action="SELL", cash_company_delta=100,
                cash_treasury_delta=-100, created_at=begin))
            await session.flush()
            await accounting.retire_company(session, company.id)
            assert company.cash == 987
            await accounting.assess_company(session, company, begin + timedelta(days=1))
            rows = (await session.scalars(select(NatNextGameTaxAssessment))).all()
            assert sum(row.amount for row in rows) == 13
            assert all(row.status == "PAID" for row in rows)
        await engine.dispose()
    asyncio.run(run())


def test_joint_expense_and_actual_supply_execution_count_without_taxing_escrow():
    async def run():
        from backend.natbirzha.models.next_game_community import NatNextGameTransfer
        from backend.natbirzha.services.next_game_civic_accounting import operating_profit
        engine, sessions = await setup()
        async with sessions() as session:
            begin = datetime(2026, 10, 1, 6)
            seller = NatNextGameCompany(owner_tg_id=97, name="Seller", cash=1000, created_at=begin)
            buyer = NatNextGameCompany(owner_tg_id=98, name="Buyer", cash=1000, created_at=begin)
            session.add_all([seller, buyer]); await session.flush()
            session.add_all([
                NatNextGameTransfer(sender_company_id=buyer.id, recipient_company_id=seller.id,
                    cash=500, reason="SUPPLY_PAYMENT", created_at=begin),
                NatNextGameLedger(company_id=seller.id, action="SUPPLY_DELIVERY", cash_company_delta=500,
                    cash_treasury_delta=-500, created_at=begin),
                NatNextGameLedger(company_id=buyer.id, action="SUPPLY_ESCROW", cash_company_delta=-900,
                    cash_treasury_delta=900, created_at=begin),
                NatNextGameLedger(company_id=buyer.id, action="JOINT_OPERATING", cash_company_delta=-40,
                    cash_treasury_delta=40, created_at=begin),
            ])
            await session.flush()
            end = begin + timedelta(days=1)
            assert await operating_profit(session, seller.id, begin, end) == 500
            assert await operating_profit(session, buyer.id, begin, end) == -540
        await engine.dispose()
    asyncio.run(run())
