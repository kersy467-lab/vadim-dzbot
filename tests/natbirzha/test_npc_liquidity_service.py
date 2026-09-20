import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import select

from backend.db.models import Base
from backend.db.session import async_session_factory, engine
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.npc import NatNpcDailyVolume
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.api.market_routes import get_npc_rates


async def run_checks():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        company = await CompanyService.create_company(session, 910001, "NPC Test One", "miner")

        # Regular NPC trading is intentionally unlimited per day. The legacy
        # population-scaling quota must not return or consume a daily counter.
        quota = await NPCReserveService.get_daily_quota(session, "iron_ore", "BUY")
        assert quota["liquidity_unlimited"] is True
        assert quota["daily_quota_per_item"] is None
        assert quota["scaling_factor"] == 1.0

        company.cash = 100000.0
        first = await NPCReserveService.execute_npc_trade(session, company, "iron_ore", "BUY", 500.0)
        second = await NPCReserveService.execute_npc_trade(session, company, "iron_ore", "BUY", 500.0)
        assert first["success"] is True and second["success"] is True
        assert first["daily_quota"] is None and second["remaining_npc_quota"] is None
        usage = (await session.execute(select(NatNpcDailyVolume))).scalars().all()
        assert usage == []

        # Regular producer sales are also unlimited, including electricity.
        inv = (await session.execute(
            select(NatInventory).where(
                NatInventory.company_id == company.id,
                NatInventory.item_id == "energy",
            )
        )).scalar_one_or_none()
        if inv is None:
            inv = NatInventory(
                company_id=company.id,
                item_id="energy",
                quantity=20000.0,
                reserved_quantity=0.0,
                avg_cost_basis=0.0,
            )
            session.add(inv)
        else:
            inv.quantity = 20000.0
        await session.flush()
        sale = await NPCReserveService.execute_npc_trade(session, company, "energy", "SELL", 12000.0)
        assert sale["success"] is True
        assert sale["daily_quota"] is None and sale["remaining_npc_quota"] is None

        rate_payload = await get_npc_rates(session)
        energy_rate = next(row for row in rate_payload["rates"] if row["item_id"] == "energy")
        assert energy_rate["daily_quota"] is None
        assert energy_rate["remaining_npc_quota"] is None
        assert energy_rate["liquidity_unlimited"] is True

        # Rare premium raw materials keep a separate small emergency stock.
        # This is not the old general liquidity limit and has its own error.
        rare_quota = await NPCReserveService.get_daily_quota(session, "lithium_raw", "BUY")
        assert rare_quota["liquidity_unlimited"] is False
        assert rare_quota["daily_quota_per_item"] == nat_settings.NPC_RARE_SELL_RESERVES["lithium_raw"]
        company.cash = 100000.0
        rare_ok = await NPCReserveService.execute_npc_trade(
            session, company, "lithium_raw", "BUY", rare_quota["daily_quota_per_item"]
        )
        assert rare_ok["success"] is True and rare_ok["remaining_npc_quota"] == 0.0
        rare_blocked = await NPCReserveService.execute_npc_trade(session, company, "lithium_raw", "BUY", 0.01)
        assert rare_blocked["success"] is False
        assert rare_blocked["reason"] == "npc_rare_reserve_empty"

        # Inventory overflow is still rejected independently from NPC liquidity.
        iron = (await session.execute(
            select(NatInventory).where(
                NatInventory.company_id == company.id,
                NatInventory.item_id == "iron_ore",
            )
        )).scalar_one()
        iron.quantity = nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM
        await session.flush()
        overflow = await NPCReserveService.execute_npc_trade(session, company, "iron_ore", "BUY", 1.0)
        assert overflow["reason"] == "inventory_overflow"

    print("NPC LIQUIDITY SERVICE: ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(run_checks())
