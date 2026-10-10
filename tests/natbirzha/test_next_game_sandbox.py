import asyncio
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.next_game_catalog import get_next_game_catalog
from backend.natbirzha.services.next_game_service import NextGameService


def test_catalog_has_a_small_starting_map_and_a_reachable_multistage_tree():
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
    branch_ids = {branch['id'] for sector in corporations for branch in sector['branches']}
    assert len(branch_ids) == 58
    branch_names = {branch['id']: branch['name'] for sector in corporations for branch in sector['branches']}
    assert all(len(branch['next_branch_ids']) == 2 for sector in corporations for branch in sector['branches'])
    assert all(target in branch_ids for sector in corporations for branch in sector['branches']
               for target in branch['next_branch_ids'])
    assert all(branch['future_choices'] == [branch_names[target] for target in branch['next_branch_ids']]
               for sector in corporations for branch in sector['branches'])
    starting = {branch['id'] for sector in corporations for branch in sector['branches']
                if branch['is_starting_branch']}
    assert len(starting) <= 20
    assert not starting.intersection({'water_forest', 'agriculture', 'food_beverages', 'logistics'})
    reachable = set(starting)
    frontier = list(starting)
    while frontier:
        current = frontier.pop()
        current_branch = next(branch for sector in corporations for branch in sector['branches']
                              if branch['id'] == current)
        for child in current_branch['next_branch_ids']:
            if child not in reachable:
                reachable.add(child)
                frontier.append(child)
    assert reachable == branch_ids


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
            with pytest.raises(ValueError, match='позже по карте'):
                await NextGameService.select_branch(session, 551001, 'agriculture')
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


def test_2_0_opens_a_real_second_branch_at_the_next_company_level():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            await NextGameService.create_company(session, 551003, 'Ветвящаяся корпорация')
            await NextGameService.select_sector(session, 551003, 'resources')
            await NextGameService.select_branch(session, 551003, 'ore_mining')
            await NextGameService.build_facility(
                session, 551003, now=datetime(2026, 10, 10, 12, 0)
            )
            with pytest.raises(ValueError, match='уровень компании'):
                await NextGameService.advance_branch(session, 551003, 'ferrous')

            company = await session.scalar(
                select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == 551003)
            )
            company.level = 2
            await session.flush()
            selected = await NextGameService.advance_branch(session, 551003, 'ferrous')
            assert selected['company']['branch_path'] == ['ore_mining', 'ferrous']
            built = await NextGameService.build_facility(
                session, 551003, branch_id='ferrous', now=datetime(2026, 10, 10, 12, 0)
            )
            assert built['facility']['branch_id'] == 'ferrous'
            with pytest.raises(ValueError, match='не открыта'):
                await NextGameService.build_facility(
                    session, 551003, branch_id='advanced_alloys'
                )

        await engine.dispose()

    asyncio.run(check())
