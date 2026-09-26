"""Joint-factory state is migration-safe and its endpoints are registered."""

import asyncio

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.api import natbirzha_router
from backend.natbirzha.api.joint_factory_routes import _contribution_sides
from backend.natbirzha.catalogs.businesses import JOINT_FACTORY_RECIPES
from backend.natbirzha.joint_factory_migration import migrate_joint_factories
from backend.natbirzha.migrations import MIGRATIONS
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.joint_factories import (
    NatJointFactory,
    NatJointFactoryProposal,
    NatJointFactorySettlement,
)


def test_joint_factory_migration_is_registered_and_repeatable():
    assert any(version == "natbirzha_v18_001_joint_factories" for version, _ in MIGRATIONS)
    assert NatJointFactory.__tablename__ == "nat_joint_factories"
    assert NatJointFactoryProposal.__tablename__ == "nat_joint_factory_proposals"
    assert NatJointFactorySettlement.__tablename__ == "nat_joint_factory_settlements"

    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(lambda sync: NatCompany.__table__.create(sync))
                await migrate_joint_factories(connection)
                await migrate_joint_factories(connection)
                names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
                assert {
                    "nat_joint_factories",
                    "nat_joint_factory_proposals",
                    "nat_joint_factory_settlements",
                } <= names
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_joint_factory_api_routes_are_registered():
    paths = {route.path for route in natbirzha_router.routes}
    assert "/natbirzha/joint-factories" in paths
    assert "/natbirzha/joint-factories/partners" in paths
    assert "/natbirzha/joint-factories/proposals" in paths
    assert "/natbirzha/joint-factories/proposals/{proposal_id}/accept" in paths
    assert "/natbirzha/joint-factories/{factory_id}/upgrade" in paths
    assert "/natbirzha/joint-factories/{factory_id}/claim" in paths


def test_joint_factory_preview_shows_each_companys_cash_and_resource_contribution():
    recipe = JOINT_FACTORY_RECIPES["joint_power_engineer_water"]
    sides = _contribution_sides(recipe, 1, [
        {"company_id": 1, "company_name": "Энергия", "specialization": "power_engineer"},
        {"company_id": 2, "company_name": "Вода", "specialization": "water"},
    ])
    assert len(sides) == 2
    assert sides[0]["cash_contribution"] == sides[1]["cash_contribution"]
    assert {side["materials"][0]["item_id"] for side in sides} == {"energy", "water"}
