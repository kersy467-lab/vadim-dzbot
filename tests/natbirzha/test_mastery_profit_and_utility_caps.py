"""Regression coverage for profit-only mastery and company utility buyback caps."""

import asyncio
from datetime import timedelta
from math import isclose

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, get_game_today
from backend.natbirzha.models.business import NatBusiness, NatBusinessIncomeDaily
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory, get_npc_sell_price
from backend.natbirzha.models.tax import NatCompanyProfitPeriod
from backend.natbirzha.services.empire_summary_service import EmpireSummaryService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.services.progression_service import mastery_xp_required_for_rank
import backend.natbirzha.services.npc_quota_service as quota_module


def test_mastery_pays_positive_margin_without_changing_goods_or_cost_basis():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        now = get_game_now().replace(hour=14, minute=0, second=0, microsecond=0)
        spec = get_business_spec("coal_open_pit")
        async with sessions() as session:
            companies, businesses = [], []
            for index, rank in enumerate((0, 5)):
                company = NatCompany(
                    user_id=981001 + index, name=f"Mastery {rank}",
                    specialization="miner", cash=100000, level=60,
                    mastery_rank=rank, mastery_xp=mastery_xp_required_for_rank(rank),
                )
                session.add(company)
                await session.flush()
                business = NatBusiness(
                    company_id=company.id, business_type=spec["id"],
                    specialization="miner", stage=1, status="ACTIVE",
                    base_income_per_hour=spec["base_income_per_hour"],
                    base_maintenance_per_hour=spec["base_maintenance_per_hour"],
                    last_settled_at=now - timedelta(hours=1),
                    health=100, efficiency=1, metadata_json={"sale_mode": "HOLD"},
                )
                session.add(business)
                session.add_all([
                    NatInventory(
                        company_id=company.id, item_id=item, quantity=10000,
                        avg_cost_basis=CANONICAL_ITEMS[item]["base_price"],
                    ) for item in spec["inputs_per_hour"]
                ])
                companies.append(company)
                businesses.append(business)
            await session.flush()
            results = [await IdleEconomyService.settle_company(
                session, company.id, now=now, _process_deals=False
            ) for company in companies]
            baseline = await session.scalar(select(NatBusinessIncomeDaily).where(
                NatBusinessIncomeDaily.business_id == businesses[0].id
            ))
            bonus = max(0, baseline.net_profit) * 0.05
            assert bonus > 0
            assert isclose(results[1]["mastery_profit_bonus_cash"], round(bonus, 2), abs_tol=0.01)
            assert isclose(companies[1].cash - companies[0].cash, round(bonus, 2), abs_tol=0.01)
            inventories = []
            for company in companies:
                rows = (await session.scalars(select(NatInventory).where(
                    NatInventory.company_id == company.id
                ))).all()
                inventories.append({r.item_id: (r.quantity, r.avg_cost_basis) for r in rows})
            assert inventories[0] == inventories[1]
            periods = (await session.scalars(select(NatCompanyProfitPeriod).where(
                NatCompanyProfitPeriod.company_id == companies[1].id
            ))).all()
            assert isclose(sum(p.net_profit for p in periods), bonus, abs_tol=0.001)
            assert all(p.maintenance_expense == 0 and p.cost_of_goods_sold == 0 for p in periods)
            repeated = await IdleEconomyService.settle_company(
                session, companies[1].id, now=now, _process_deals=False
            )
            assert repeated["mastery_profit_bonus_cash"] == 0
            zero = EmpireSummaryService._serialize_business(businesses[0], {}, mastery_bonus_rate=0)
            five = EmpireSummaryService._serialize_business(businesses[1], {}, mastery_bonus_rate=0.05)
            assert zero["inputs_per_hour"] == five["inputs_per_hour"]
            assert zero["outputs_per_hour"] == five["outputs_per_hour"]
            expected = zero["estimated_profit_before_tax_per_hour"] * 1.05
            assert isclose(five["estimated_profit_before_tax_per_hour"], expected, abs_tol=0.02)
        await engine.dispose()
    asyncio.run(check())


def test_utility_buyback_caps_are_separate_per_company_item_and_day(monkeypatch):
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        today = get_game_today()
        monkeypatch.setattr(quota_module, "get_game_today", lambda: today)
        async with sessions() as session:
            companies = [NatCompany(user_id=982001+i, name=f"Utility {i}",
                                    specialization="power_engineer", cash=1000000) for i in range(2)]
            session.add_all(companies)
            await session.flush()
            for company in companies:
                session.add_all([NatInventory(company_id=company.id, item_id=item, quantity=quantity,
                                              avg_cost_basis=0)
                                 for item, quantity in (("energy", 40000), ("water", 200000), ("iron_ore", 10000))])
            await session.flush()
            assert get_npc_sell_price("energy") == 12.5
            sale = await NPCReserveService.execute_npc_trade(session, companies[0], "energy", "SELL", 37500)
            assert sale["success"] and sale["total_payout"] == 300000
            assert sale["remaining_npc_cash_quota"] == 0
            blocked = await NPCReserveService.execute_npc_trade(session, companies[0], "energy", "SELL", 1)
            assert not blocked["success"] and blocked["reason"] == "npc_daily_quota_exceeded"
            other = await NPCReserveService.execute_npc_trade(session, companies[1], "energy", "SELL", 1)
            assert other["success"] and other["remaining_npc_cash_quota"] == 299992
            water = await NPCReserveService.execute_npc_trade(session, companies[0], "water", "SELL", 187500)
            assert water["success"] and water["total_payout"] == 300000
            ordinary = await NPCReserveService.execute_npc_trade(session, companies[0], "iron_ore", "SELL", 1000)
            assert ordinary["success"] and ordinary["daily_quota"] is None
            monkeypatch.setattr(quota_module, "get_game_today", lambda: today + timedelta(days=1))
            statuses = await NPCReserveService.get_quota_statuses(
                session, ["energy", "water"], "SELL", company_id=companies[0].id
            )
            assert all(s["remaining_npc_cash_quota"] == 300000 for s in statuses.values())
            renewed = await NPCReserveService.execute_npc_trade(session, companies[0], "energy", "SELL", 1)
            assert renewed["success"] and renewed["remaining_npc_cash_quota"] == 299992
        await engine.dispose()
    asyncio.run(check())
