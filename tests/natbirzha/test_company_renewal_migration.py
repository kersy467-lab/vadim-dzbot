import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from backend.natbirzha.migrations import _migrate_v24_company_renewal


def test_renewal_migration_preserves_company_and_is_repeatable():
    async def check():
        engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.execute(text('CREATE TABLE nat_companies (id INTEGER PRIMARY KEY, cash FLOAT)'))
            await conn.execute(text('INSERT INTO nat_companies (id,cash) VALUES (1,987654.32)'))
            await _migrate_v24_company_renewal(conn)
            await _migrate_v24_company_renewal(conn)
            row=(await conn.execute(text('SELECT cash,rebirth_count,last_rebirth_at FROM nat_companies WHERE id=1'))).one()
            assert row.cash==987654.32 and row.rebirth_count==0 and row.last_rebirth_at is None
            tables=set((await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).scalars())
            assert {'nat_company_rebirths','nat_company_aid_requests','nat_company_aid_transfers'} <= tables
        await engine.dispose()
    asyncio.run(check())
