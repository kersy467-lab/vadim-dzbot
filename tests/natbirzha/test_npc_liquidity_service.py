import asyncio
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from sqlalchemy import select

from backend.db.models import Base
from backend.db.session import async_session_factory, engine
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.npc import NatNpcDailyVolume
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.api.market_routes import get_npc_rates
import backend.natbirzha.services.npc_service as npc_service_module
import backend.natbirzha.services.npc_quota_service as npc_quota_module


async def run_checks():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        company = await CompanyService.create_company(session, 910001, "NPC Test One", "miner")

        # NPC buyback liquidity is unlimited; sell quota error npc_daily_quota_exceeded is disabled.
        quota = await NPCReserveService.get_daily_quota(session, "iron_ore", "BUY")
        assert quota["liquidity_unlimited"] is True
        assert quota["daily_quota_per_item"] is None
        assert quota["scaling_factor"] == 1.0

        sell_quota = await NPCReserveService.get_daily_quota(session, "energy", "SELL")
        assert sell_quota["liquidity_unlimited"] is True
        assert sell_quota["daily_quota_per_item"] is None
        assert sell_quota["daily_quota_cash"] is None

        company.cash = 100000.0
        first = await NPCReserveService.execute_npc_trade(session, company, "iron_ore", "BUY", 500.0)
        second = await NPCReserveService.execute_npc_trade(session, company, "iron_ore", "BUY", 500.0)
        assert first["success"] is True and second["success"] is True
        assert first["daily_quota"] is None and second["remaining_npc_quota"] is None
        usage = (await session.execute(select(NatNpcDailyVolume))).scalars().all()
        assert usage == []

        # Unlimited producer sales to NPC: no quota cap on sales.
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
                quantity=30000.0,
                reserved_quantity=0.0,
                avg_cost_basis=0.0,
            )
            session.add(inv)
        else:
            inv.quantity = 30000.0
        await session.flush()

        unit_buy_price = NPCReserveService.get_npc_quote("energy")["npc_buy_price"]
        sale = await NPCReserveService.execute_npc_trade(
            session, company, "energy", "SELL", 20000.0
        )
        assert sale["success"] is True
        assert sale["daily_quota"] is None
        assert sale["total_payout"] == round(20000.0 * unit_buy_price, 2)

        # Subsequent sale also succeeds without npc_daily_quota_exceeded error
        subsequent_sale = await NPCReserveService.execute_npc_trade(
            session, company, "energy", "SELL", 5000.0
        )
        assert subsequent_sale["success"] is True
        assert subsequent_sale["total_payout"] == round(5000.0 * unit_buy_price, 2)

        rate_payload = await get_npc_rates(session)
        energy_rate = next(row for row in rate_payload["rates"] if row["item_id"] == "energy")
        assert energy_rate["daily_quota"] is None
        assert energy_rate["player_sell_daily_quota"] is None
        assert energy_rate["player_sell_remaining_quota"] is None
        assert energy_rate["player_sell_quota_label"] == "Скупка Госрезервом: без ограничений"

        # Check precision validation still works
        fractional_sale = await NPCReserveService.execute_npc_trade(
            session, company, "energy", "SELL", 0.001
        )
        assert fractional_sale["success"] is False
        assert fractional_sale["reason"] == "invalid_quantity_precision"

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
