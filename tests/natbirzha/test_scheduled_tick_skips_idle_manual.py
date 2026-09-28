"""No-op factory cycles are skipped by the scheduled and login catch-up paths."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.production_service import ProductionTickEngine


async def _select_count_for_future_manual_factory(use_login_catchup: bool) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime(2026, 9, 28, 12)
    statements = []

    def count_select(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().lower().startswith("select"):
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", count_select)
    try:
        async with sessions() as session:
            company = NatCompany(
                user_id=993_481,
                name="Idle Manual Factory",
                specialization="power_engineer",
                level=1,
                cash=10_000,
            )
            session.add(company)
            await session.flush()
            session.add(NatFactory(
                company_id=company.id,
                building_type="solar_plant",
                specialization="power_engineer",
                level=1,
                automation_enabled=False,
                cycle_ready_at=now + timedelta(minutes=30),
            ))
            await session.commit()

            statements.clear()
            if use_login_catchup:
                result = await ProductionTickEngine.catch_up_company(
                    session, company.id, now=now
                )
                assert result == []
            else:
                result = await ProductionTickEngine.process_global_scheduled_tick(
                    session, now=now
                )
                assert result["ticks_processed"] == 0

            # Only the initial due-work scan should run; no row locks/queries for a cycle not yet ready.
            assert len(statements) == 1, statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_select)
        await engine.dispose()


def test_login_catchup_skips_manual_factories_that_are_not_due():
    asyncio.run(_select_count_for_future_manual_factory(use_login_catchup=True))


def test_global_tick_skips_manual_factories_that_are_not_due():
    asyncio.run(_select_count_for_future_manual_factory(use_login_catchup=False))
