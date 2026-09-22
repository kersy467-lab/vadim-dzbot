"""Schema contracts for the rollout-safe NATBIRZHA 2.0 foundation."""

import asyncio

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401 - registers all game tables
from backend.natbirzha.models.business import BUSINESS_STATUSES, NatBusiness


REQUIRED_TABLES = {
    "nat_businesses",
    "nat_business_supply_policies",
    "nat_business_vehicles",
    "nat_business_employees",
    "nat_business_projects",
    "nat_business_income_daily",
    "nat_company_economy_states",
    "nat_military_infrastructure",
    "nat_army_trainings",
    "nat_tax_daily",
}


def test_tycoon_v2_tables_and_business_defaults_are_registered() -> None:
    assert REQUIRED_TABLES <= set(Base.metadata.tables)
    assert NatBusiness.__table__.c.stage.default.arg == 1
    assert NatBusiness.__table__.c.status.default.arg == "ACTIVE"
    assert {"ACTIVE", "UPGRADING", "PAUSED_MANUAL", "PAUSED_SUPPLY"} <= BUSINESS_STATUSES


def test_tycoon_v2_schema_has_required_indexes_and_supply_uniqueness() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

            def inspect_schema(sync_connection):
                inspector = inspect(sync_connection)
                business_indexes = {row["name"] for row in inspector.get_indexes("nat_businesses")}
                supply_constraints = inspector.get_unique_constraints("nat_business_supply_policies")
                return business_indexes, supply_constraints

            business_indexes, supply_constraints = await connection.run_sync(inspect_schema)
        await engine.dispose()

        assert {"ix_nat_businesses_company_id", "ix_nat_businesses_business_type", "ix_nat_businesses_status"} <= business_indexes
        assert any(set(row["column_names"]) == {"business_id", "item_id"} for row in supply_constraints)

    asyncio.run(check())
