"""Bankruptcy breaches a partnership and moves the seized share to the State market."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import JOINT_FACTORY_RECIPES
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.joint_factories import NatJointFactory, NatJointFactorySettlement
from backend.natbirzha.services.bankruptcy_market_service import BankruptcyMarketService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.joint_factory_service import JointFactoryService
from backend.natbirzha.services.joint_factory_settlement_service import JointFactorySettlementService


NOW = datetime(2026, 9, 26, 12)
RECIPE_ID = "joint_power_engineer_water"


def test_bankruptcy_stops_production_seizes_shared_stock_and_leaves_partner_share_claimable():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            async with sessions() as session:
                users = [
                    User(tg_id=991101, full_name="Power"),
                    User(tg_id=991102, full_name="Water"),
                ]
                session.add_all(users)
                await session.flush()
                companies = [
                    NatCompany(user_id=users[0].id, name="Power Co", specialization="power_engineer", cash=1_000_000),
                    NatCompany(user_id=users[1].id, name="Water Co", specialization="water", cash=1_000_000),
                ]
                session.add_all(companies)
                await session.flush()
                recipe = JOINT_FACTORY_RECIPES[RECIPE_ID]
                for company in companies:
                    for item_id, quantity in recipe["levels"][0]["contributions"][company.specialization]["resources"].items():
                        session.add(NatInventory(
                            company_id=company.id, item_id=item_id, quantity=float(quantity) * 4,
                            reserved_quantity=0, avg_cost_basis=1,
                        ))
                await session.flush()
                ids = [company.id for company in companies]
                proposal = await JointFactoryService.create_build_proposal(
                    session, ids[0], ids[1], RECIPE_ID, now=NOW
                )
                accepted = await JointFactoryService.accept_proposal(
                    session, ids[1], proposal["proposal_id"], now=NOW
                )
                factory = await session.get(NatJointFactory, accepted["factory_id"])
                await IdleEconomyService.settle_company(
                    session, ids[0], now=NOW + timedelta(hours=2)
                )
                power_share = dict(factory.stock_a_json)
                water_share = dict(factory.stock_b_json)
                await JointFactorySettlementService.breach_for_company(
                    session, ids[0], now=NOW + timedelta(hours=2)
                )
                lots = await BankruptcyMarketService.list_confiscated_assets(
                    session, companies[0], "joint-bankruptcy-test"
                )
                goods_lots = [lot for lot in lots if lot.asset_kind == "JOINT_GOODS"]
                assert len(goods_lots) == len(power_share)
                assert all(lot.quantity == pytest.approx(power_share[lot.asset_type] * 0.70) for lot in goods_lots)
                assert factory.status == "BREACHED"
                assert dict(factory.stock_a_json) == pytest.approx(
                    {item: quantity * 0.30 for item, quantity in power_share.items()}
                )
                treasury = await session.get(NatStateTreasury, 1)
                starting_treasury_cash = float(treasury.cash) if treasury else 10_000_000.0
                lot = goods_lots[0]
                purchase = await BankruptcyMarketService.purchase_lot(
                    session, company_id=ids[1], lot_id=lot.id, now=NOW + timedelta(hours=2), commit=False
                )
                assert purchase["success"] is True
                assert purchase["asset_kind"] == "JOINT_GOODS"
                updated_treasury = await session.get(NatStateTreasury, 1)
                assert updated_treasury.cash > starting_treasury_cash
                survivor_claim = await JointFactoryService.claim_output(
                    session, ids[1], factory.id, now=NOW + timedelta(hours=3)
                )
                assert survivor_claim["claimed"] == pytest.approx(water_share)
                assert await session.scalar(select(NatJointFactorySettlement.id)) is not None
        finally:
            await engine.dispose()

    asyncio.run(check())
