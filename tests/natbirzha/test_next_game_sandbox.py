import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.next_game_catalog import get_next_game_catalog
from backend.natbirzha.services.next_game_service import NextGameService


def test_catalog_has_seven_distinct_parent_corporations_and_valid_entry_branches():
    corporations = get_next_game_catalog()
    assert [item['id'] for item in corporations] == [
        'resources', 'energy', 'oilgas', 'materials', 'infrastructure', 'technology', 'bank',
    ]
    assert all(len(item['branches']) >= 3 for item in corporations)
    assert len({branch['id'] for sector in corporations for branch in sector['branches']}) == sum(
        len(sector['branches']) for sector in corporations
    )
    assert all(branch['outputs'] and len(branch['future_choices']) >= 2
               for sector in corporations for branch in sector['branches'])


def test_admin_sandbox_choices_are_persistent_isolated_and_not_respecable():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            legacy = NatCompany(user_id=722001, name='Legacy Player', specialization='miner', cash=777)
            session.add(legacy)
            await session.commit()
            old_level, old_cash = legacy.level, legacy.cash

            created = await NextGameService.create_company(session, 551001, 'Тест 2.0')
            selected = await NextGameService.select_sector(session, 551001, 'resources')
            branch = await NextGameService.select_branch(session, 551001, 'ore_mining')
            snapshot = await NextGameService.snapshot(session, 551001)

            assert created['company']['cash'] == 10_000
            assert selected['company']['sector_id'] == 'resources'
            assert branch['company']['branch_path'] == ['ore_mining']
            assert snapshot['company']['branch_path'] == ['ore_mining']
            assert legacy.level == old_level and legacy.cash == old_cash
            assert await NextGameService.snapshot(session, 551002) == {
                'company': None, 'corporations': get_next_game_catalog(),
            }
            with pytest.raises(ValueError, match='уже выбрана'):
                await NextGameService.select_sector(session, 551001, 'energy')
            with pytest.raises(ValueError, match='не относится'):
                await NextGameService.select_branch(session, 551001, 'nuclear')

        await engine.dispose()

    asyncio.run(check())
