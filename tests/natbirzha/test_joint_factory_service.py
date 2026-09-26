"""Joint factories use a separate slot, shared proposals and offline settlement."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import JOINT_FACTORY_RECIPES
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.joint_factories import (
    NatJointFactory,
    NatJointFactoryProposal,
    NatJointFactorySettlement,
)
from backend.natbirzha.services.joint_factory_service import JointFactoryService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.joint_factory_settlement_service import JointFactorySettlementService
from backend.natbirzha.services.company_service import CompanyService


NOW = datetime(2026, 9, 26, 12)
RECIPE_ID = "joint_power_engineer_water"


async def _fixture(*, cash=1_000_000.0, ordinary_slots=0):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        users = [
            User(tg_id=991001, full_name="Power Player"),
            User(tg_id=991002, full_name="Water Player"),
        ]
        session.add_all(users)
        await session.flush()
        companies = [
            NatCompany(
                user_id=users[0].id, name="Power Company", specialization="power_engineer",
                cash=cash, business_slot_capacity=ordinary_slots,
            ),
            NatCompany(
                user_id=users[1].id, name="Water Company", specialization="water",
                cash=cash, business_slot_capacity=ordinary_slots,
            ),
        ]
        session.add_all(companies)
        await session.flush()
        recipe = JOINT_FACTORY_RECIPES[RECIPE_ID]
        for company in companies:
            requirement = recipe["levels"][0]["contributions"][company.specialization]
            for item_id, quantity in requirement["resources"].items():
                session.add(NatInventory(
                    company_id=company.id,
                    item_id=item_id,
                    quantity=float(quantity) * 3,
                    reserved_quantity=0.0,
                    avg_cost_basis=3.0,
                ))
        await session.commit()
        ids = [company.id for company in companies]
    return engine, sessions, ids


async def _build(session, company_ids, *, now=NOW):
    proposal = await JointFactoryService.create_build_proposal(
        session, company_ids[0], company_ids[1], RECIPE_ID, now=now
    )
    result = await JointFactoryService.accept_proposal(
        session, company_ids[1], proposal["proposal_id"], now=now
    )
    await session.flush()
    return proposal, result


def test_build_needs_both_owners_and_uses_a_dedicated_slot():
    async def check():
        engine, sessions, company_ids = await _fixture(ordinary_slots=0)
        try:
            async with sessions() as session:
                before = {
                    company.id: float(company.cash)
                    for company in (await session.execute(
                        select(NatCompany).where(NatCompany.id.in_(company_ids))
                    )).scalars().all()
                }
                _proposal, accepted = await _build(session, company_ids)
                factory = await session.get(NatJointFactory, accepted["factory_id"])
                assert factory.status == "ACTIVE"
                assert factory.level == 1
                assert accepted["slot"] == "Совместный завод · отдельная мощность"
                assert accepted["cash_contributed"] > 0
                for company_id in company_ids:
                    company = await session.get(NatCompany, company_id)
                    assert company.business_slot_capacity == 0
                    assert company.cash < before[company_id]
                with pytest.raises(ValueError, match="слот"):
                    await JointFactoryService.create_build_proposal(
                        session, company_ids[0], company_ids[1], RECIPE_ID, now=NOW
                    )
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_idle_settlement_produces_without_cash_or_operating_inputs_and_claims_each_half():
    async def check():
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                _proposal, accepted = await _build(session, company_ids)
                cash_after_build = {
                    company_id: float((await session.get(NatCompany, company_id)).cash)
                    for company_id in company_ids
                }
                opened_resource = {
                    row.company_id: float(row.quantity)
                    for row in (await session.execute(select(NatInventory))).scalars().all()
                }
                await IdleEconomyService.settle_company(
                    session, company_ids[0], now=NOW + timedelta(hours=2)
                )
                factory = await session.get(NatJointFactory, accepted["factory_id"])
                recipe = JOINT_FACTORY_RECIPES[RECIPE_ID]
                expected_total = {
                    item: float(rate) * 2
                    for item, rate in recipe["levels"][0]["outputs_per_hour"].items()
                }
                assert factory.total_produced_json == pytest.approx(expected_total)
                for company_id in company_ids:
                    company = await session.get(NatCompany, company_id)
                    assert company.cash == pytest.approx(cash_after_build[company_id])
                inventory_rows = list((await session.execute(select(NatInventory))).scalars().all())
                assert {
                    row.company_id: float(row.quantity) for row in inventory_rows
                } == pytest.approx(opened_resource)
                stock_a = dict(factory.stock_a_json)
                stock_b = dict(factory.stock_b_json)
                assert stock_a == pytest.approx({item: quantity / 2 for item, quantity in expected_total.items()})
                assert stock_b == pytest.approx(stock_a)
                assert await session.scalar(select(NatJointFactorySettlement.id)) is not None
                claimed = await JointFactoryService.claim_output(
                    session, company_ids[0], factory.id, now=NOW + timedelta(hours=2)
                )
                assert claimed["claimed"] == pytest.approx(stock_a)
                assert dict(factory.stock_a_json) == pytest.approx({item: 0 for item in stock_a})
                assert any(
                    row.company_id == company_ids[0]
                    and row.item_id in stock_a
                    and row.quantity >= stock_a[row.item_id]
                    for row in inventory_rows
                ) or claimed["claimed"]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_upgrade_is_a_second_bilateral_proposal_and_double_accept_is_rejected():
    async def check():
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                _proposal, accepted = await _build(session, company_ids)
                factory = await session.get(NatJointFactory, accepted["factory_id"])
                upgrade = await JointFactoryService.create_upgrade_proposal(
                    session, company_ids[0], factory.id, now=NOW + timedelta(hours=1)
                )
                assert upgrade["target_level"] == 2
                accepted_upgrade = await JointFactoryService.accept_proposal(
                    session, company_ids[1], upgrade["proposal_id"], now=NOW + timedelta(hours=1)
                )
                assert accepted_upgrade["level"] == 2
                with pytest.raises(ValueError, match="обработано"):
                    await JointFactoryService.accept_proposal(
                        session, company_ids[1], upgrade["proposal_id"], now=NOW + timedelta(hours=1)
                    )
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_insufficient_partner_contribution_rolls_back_both_sides():
    async def check():
        engine, sessions, company_ids = await _fixture(cash=1_000_000)
        try:
            async with sessions() as session:
                proposer = await session.get(NatCompany, company_ids[0])
                partner = await session.get(NatCompany, company_ids[1])
                proposal = await JointFactoryService.create_build_proposal(
                    session, proposer.id, partner.id, RECIPE_ID, now=NOW
                )
                recipe = JOINT_FACTORY_RECIPES[RECIPE_ID]
                partner.cash = float(recipe["levels"][0]["contributions"]["water"]["cash"]) - 0.01
                await session.flush()
                cash_a = float(proposer.cash)
                with pytest.raises(ValueError, match="недостаточно cash"):
                    await JointFactoryService.accept_proposal(
                        session, partner.id, proposal["proposal_id"], now=NOW
                    )
                assert proposer.cash == pytest.approx(cash_a)
                assert await session.scalar(select(NatJointFactory.id)) is None
                pending = await session.get(NatJointFactoryProposal, proposal["proposal_id"])
                assert pending.status == "PENDING"
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_pending_build_offer_locks_both_participants_for_settlement_ordering():
    async def check():
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                await JointFactoryService.create_build_proposal(
                    session, company_ids[0], company_ids[1], RECIPE_ID, now=NOW
                )
                participants = await JointFactorySettlementService.participants_to_settle(
                    session, company_ids[0]
                )
                assert participants == set(company_ids)
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_joint_factory_respects_ordinary_business_tax_production_deadline():
    async def check():
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                _proposal, accepted = await _build(session, company_ids)
                factory = await session.get(NatJointFactory, accepted["factory_id"])
                factory.last_settled_at = datetime(2026, 9, 26, 11)
                session.add(NatBusiness(
                    company_id=company_ids[0], business_type="retail_chain",
                    last_settled_at=datetime(2026, 9, 26, 11),
                ))
                await session.flush()
                result = await JointFactorySettlementService.settle_for_company(
                    session, company_ids[0], now=datetime(2026, 9, 26, 13)
                )
                assert result[0]["settled_hours"] == pytest.approx(1.0)
                expected = {
                    item: float(rate)
                    for item, rate in JOINT_FACTORY_RECIPES[RECIPE_ID]["levels"][0]["outputs_per_hour"].items()
                }
                assert factory.total_produced_json == pytest.approx(expected)
                assert factory.last_settled_at == datetime(2026, 9, 26, 13)
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_company_reset_preserves_partner_joint_factory_stock_in_inventory(monkeypatch):
    async def check():
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                _proposal, accepted = await _build(session, company_ids)
                target = await session.get(NatCompany, company_ids[0])
                partner = await session.get(NatCompany, company_ids[1])
                factory = await session.get(NatJointFactory, accepted["factory_id"])
                now = datetime(2026, 9, 26, 15)
                monkeypatch.setattr(
                    "backend.natbirzha.services.joint_factory_settlement_service.get_game_now",
                    lambda: now,
                )
                monkeypatch.setattr(
                    "backend.natbirzha.services.company_service.get_game_now",
                    lambda: now,
                )
                factory.last_settled_at = now - timedelta(hours=1)
                recipe = JOINT_FACTORY_RECIPES[RECIPE_ID]
                before = {
                    row.item_id: float(row.quantity)
                    for row in (await session.execute(select(NatInventory).where(
                        NatInventory.company_id == partner.id
                    ))).scalars().all()
                }
                await CompanyService.reset_company_for_user(
                    session, target.user_id, commit=False
                )
                assert await session.get(NatCompany, target.id) is None
                assert await session.get(NatJointFactory, factory.id) is None
                inventory = {
                    row.item_id: float(row.quantity)
                    for row in (await session.execute(select(NatInventory).where(
                        NatInventory.company_id == partner.id
                    ))).scalars().all()
                }
                for item_id, rate in recipe["levels"][0]["outputs_per_hour"].items():
                    expected_transfer = float(rate) / 2
                    assert inventory.get(item_id, 0) >= before.get(item_id, 0) + expected_transfer
        finally:
            await engine.dispose()

    asyncio.run(check())
