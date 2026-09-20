"""Pure-service verification for NATBIRZHA P0 hardening.

This intentionally avoids importing backend.main so it can verify core invariants
without starting the Telegram bot/application layer.
"""

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

from backend.db.models import Base
from backend.db.session import async_session_factory, engine
from backend.natbirzha.config import get_game_now, nat_settings
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.auth_service import validate_test_init_data
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.upgrade_service import UpgradeService


def signed_test_init_data(tg_id: int) -> str:
    values = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": tg_id, "first_name": "P0"}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", nat_settings.TEST_AUTH_SECRET.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(values)


async def reset_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def company(session, uid: int, spec: str = "agrarian") -> NatCompany:
    return await CompanyService.create_company(
        session,
        uid,
        f"P0 Corp {uid}",
        spec,
        commit=True,
    )


async def run() -> None:
    await reset_database()

    # Auth: unsigned payload is never an accepted test credential.
    old_test_auth = nat_settings.ALLOW_TEST_AUTH
    try:
        nat_settings.ALLOW_TEST_AUTH = True
        unsigned = urllib.parse.urlencode({"user": json.dumps({"id": 101})})
        assert validate_test_init_data(unsigned) is None
        signed = signed_test_init_data(101)
        assert validate_test_init_data(signed)["user"]["id"] == 101
        nat_settings.ALLOW_TEST_AUTH = False
        assert validate_test_init_data(signed) is None
    finally:
        nat_settings.ALLOW_TEST_AUTH = old_test_auth

    # Company: every player company starts with the same 10k cash; state money is separate.
    async with async_session_factory() as session:
        comp = await company(session, 2001)
        assert comp.cash == nat_settings.STARTING_CASH == 10000.0
        factory = (await session.execute(
            select(NatFactory).where(NatFactory.company_id == comp.id)
        )).scalar_one()
        assert factory.current_recipe is None
        assert factory.cycle_started_at is None
        assert factory.cycle_ready_at is None
        factory.last_produced_at = get_game_now() - timedelta(days=2)
        await session.commit()
        company_id = comp.id
        factory_id = factory.id

    # Offline catch-up may not invent a cycle just because time passed.
    async with async_session_factory() as session:
        before = (await session.execute(
            select(NatInventory).where(
                NatInventory.company_id == company_id,
                NatInventory.item_id == "grain",
            )
        )).scalar_one_or_none()
        before_qty = before.quantity if before else 0.0
        completed = await ProductionTickEngine.catch_up_company(
            session, company_id, now=get_game_now()
        )
        after = (await session.execute(
            select(NatInventory).where(
                NatInventory.company_id == company_id,
                NatInventory.item_id == "grain",
            )
        )).scalar_one_or_none()
        assert completed == []
        assert (after.quantity if after else 0.0) == before_qty

    # A ready cycle must not overfill the authoritative inventory cap.
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, company_id)
        factory = await session.get(NatFactory, factory_id)
        grain = NatInventory(
            company_id=company_id, item_id="grain",
            quantity=nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM - 1.0,
            reserved_quantity=0.0, avg_cost_basis=0.0,
        )
        session.add(grain)
        await session.flush()
        started = await ProductionTickEngine.start_cycle(
            session, comp, factory, recipe_id="farm_grain", now=get_game_now()
        )
        assert started["success"]
        factory = await session.get(NatFactory, factory_id)
        blocked = await ProductionTickEngine.complete_cycle(
            session, comp, factory, now=factory.cycle_ready_at
        )
        assert blocked["success"] is False and blocked["reason"] == "inventory_overflow"
        await session.rollback()

    # Workers and technology must have a real server-side throughput effect.
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, company_id)
        factory = await session.get(NatFactory, factory_id)
        base = ProductionTickEngine.output_multiplier(factory)
        comp.level = 5
        comp.cash = 100000.0
        await session.commit()
        await UpgradeService.upgrade(session, comp, factory.id, "workers")
        await session.commit()
        factory = await session.get(NatFactory, factory_id)
        workers_mult = ProductionTickEngine.output_multiplier(factory)
        assert workers_mult > base
        await UpgradeService.upgrade(session, comp, factory.id, "technology")
        await session.commit()
        factory = await session.get(NatFactory, factory_id)
        assert ProductionTickEngine.output_multiplier(factory) > workers_mult

    # Regular NPC liquidity has no daily or population-scaled limit.
    async with async_session_factory() as session:
        q1 = await NPCReserveService.get_daily_quota(session, "grain", "BUY")
        assert q1["scaling_factor"] == 1.0
        assert q1["liquidity_unlimited"] is True
        assert q1["daily_quota_per_item"] is None
        for uid in range(2002, 2022):
            await company(session, uid)
        q21 = await NPCReserveService.get_daily_quota(session, "grain", "BUY")
        assert q21["scaling_factor"] == 1.0
        assert q21["daily_quota_per_item"] is None

    # Multiple large regular trades remain available on the same game day.
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, company_id)
        comp.cash = 100000.0
        first = await NPCReserveService.execute_npc_trade(session, comp, "grain", "BUY", 250.0)
        second = await NPCReserveService.execute_npc_trade(session, comp, "grain", "BUY", 250.0)
        assert first["success"] is True and second["success"] is True
        assert first["remaining_npc_quota"] is None and second["remaining_npc_quota"] is None
        await session.rollback()

    # P2P matching settles atomically and cannot bypass the same inventory cap.
    async with async_session_factory() as session:
        buyer = await session.get(NatCompany, company_id)
        seller = (await session.execute(
            select(NatCompany).where(NatCompany.user_id == 2002)
        )).scalar_one()
        seller_steel = NatInventory(
            company_id=seller.id, item_id="steel", quantity=5.0,
            reserved_quantity=0.0, avg_cost_basis=50.0,
        )
        session.add(seller_steel)
        buyer.cash = 100000.0
        await session.commit()

        seller_cash_before = seller.cash
        buyer_cash_before = buyer.cash
        await MarketService.create_order(session, seller, "SELL", "steel", 100.0, 2.0)
        buy = await MarketService.create_order(session, buyer, "BUY", "steel", 100.0, 2.0)
        assert buy.status == "FILLED"
        await session.refresh(buyer)
        await session.refresh(seller)
        buyer_steel = (await session.execute(select(NatInventory).where(
            NatInventory.company_id == buyer.id, NatInventory.item_id == "steel"
        ))).scalar_one()
        assert buyer_steel.quantity == 2.0
        assert buyer.cash == buyer_cash_before - 200.0
        assert seller.cash == seller_cash_before + 198.0

        buyer_steel.quantity = nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM
        seller_steel = (await session.execute(select(NatInventory).where(
            NatInventory.company_id == seller.id, NatInventory.item_id == "steel"
        ))).scalar_one()
        seller_steel.quantity = 5.0
        buyer_before_overflow_order = buyer.cash
        await session.commit()
        await MarketService.create_order(session, seller, "SELL", "steel", 101.0, 1.0)
        overflow_buy = await MarketService.create_order(session, buyer, "BUY", "steel", 101.0, 1.0)
        assert overflow_buy.status == "CANCELLED"
        await session.refresh(buyer)
        assert buyer.cash == buyer_before_overflow_order

    # Idempotency record and business mutation commit atomically and replay from cache.
    async with async_session_factory() as session:
        comp = await session.get(NatCompany, company_id)
        comp.cash -= 123.0
        response = {"success": True, "remaining_cash": comp.cash}
        committed = await IdempotencyService.commit_response(
            session,
            user_id=comp.user_id,
            endpoint="/p0/test",
            idempotency_key="same-key",
            payload={"amount": 123},
            response_body=response,
        )
        assert committed == response

    async with async_session_factory() as session:
        cached = await IdempotencyService.check_or_conflict(
            session, 2001, "/p0/test", "same-key", {"amount": 123}
        )
        assert cached and cached[1]["remaining_cash"] == response["remaining_cash"]
        try:
            await IdempotencyService.check_or_conflict(
                session, 2001, "/p0/test", "same-key", {"amount": 999}
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Reusing an idempotency key with a different payload must conflict")

    print("NATBIRZHA P0 hardening service checks: PASS")


if __name__ == "__main__":
    asyncio.run(run())
