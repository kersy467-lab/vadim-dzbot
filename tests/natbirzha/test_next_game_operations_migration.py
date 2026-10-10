import asyncio
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import create_async_engine
from backend.db.models import Base
import backend.natbirzha.models
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.next_game_operations_migration import migrate_next_game_operations


def test_new_service_migration_preserves_existing_company_and_is_repeatable():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(lambda sync: Base.metadata.create_all(sync,
                    tables=[NatNextGameCompany.__table__, NatNextGameFacility.__table__]))
                await connection.execute(NatNextGameCompany.__table__.insert().values(id=1,
                    owner_tg_id=981004, name="Сохранение до миграции", cash=12345.0051,
                    branch_path=["thermal"], sector_id="energy", level=8, xp=7000))
                await migrate_next_game_operations(connection)
                await migrate_next_game_operations(connection)
                company = (await connection.execute(select(NatNextGameCompany.__table__))).mappings().one()
                assert company["cash"] == 12345.0051 and company["branch_path"] == ["thermal"]
                assert company["level"] == 8 and company["xp"] == 7000
                tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
                for name in ("operations", "factory_operations", "employees", "vehicles", "tax_accounts",
                             "tax_assessments", "city_orders", "economic_events", "bankruptcies",
                             "liquidation_lots", "debt_writeoffs"):
                    assert f"nat_next_game_{name}" in tables
        finally:
            await engine.dispose()
    asyncio.run(check())
