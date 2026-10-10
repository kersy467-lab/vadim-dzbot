import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameDeposit, NatNextGameLedger,
    NatNextGameLoan, NatNextGameTreasury,
)
from backend.natbirzha.next_game_economy_migration import migrate_next_game_bank, migrate_next_game_economy
from backend.natbirzha.next_game_deposit_migration import migrate_next_game_deposits
from backend.natbirzha.next_game_equity_migration import migrate_next_game_equity
from backend.natbirzha.next_game_banking_migration import migrate_next_game_banking
from backend.natbirzha.next_game_finance_migration import migrate_next_game_finance
from backend.natbirzha.next_game_catalog import (
    CUSTOM_ITEMS, NEXT_GAME_BASE_PRICES, get_next_game_catalog, get_next_game_items,
)
from backend.natbirzha.services.next_game_service import BUY_MARKUP, SELL_MARKDOWN, NextGameService


def test_every_branch_has_a_marketable_factory_recipe_and_frozen_item_price():
    from backend.natbirzha.models.inventory import CANONICAL_ITEMS

    assert set(CANONICAL_ITEMS) <= set(NEXT_GAME_BASE_PRICES)
    branches = [branch for sector in get_next_game_catalog() for branch in sector['branches']]
    assert len(branches) >= 24
    for branch in branches:
        recipe = branch['factory']
        assert recipe['build_cost'] > 0
        assert recipe['cycle_seconds'] >= 60
        assert recipe['output_item'] in get_next_game_items()
        assert recipe['output_item'] in NEXT_GAME_BASE_PRICES or recipe['output_item'] in CUSTOM_ITEMS
        assert recipe['output_quantity'] > 0
        assert all(item in get_next_game_items() for item in recipe['inputs'])
        assert all(item in NEXT_GAME_BASE_PRICES or item in CUSTOM_ITEMS for item in recipe['inputs'])


def test_every_factory_covers_npc_inputs_and_cycle_costs():
    items = get_next_game_items()
    branches = [branch for sector in get_next_game_catalog() for branch in sector['branches']]
    for branch in branches:
        recipe = branch['factory']
        revenue = items[recipe['output_item']]['base_price'] * recipe['output_quantity'] * SELL_MARKDOWN
        inputs = sum(items[item_id]['base_price'] * amount * BUY_MARKUP
                     for item_id, amount in recipe['inputs'].items())
        assert revenue > inputs + recipe['operating_cost'], branch['id']


def test_admin_game_builds_produces_and_trades_without_touching_legacy_economy():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        now = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            legacy = NatCompany(user_id=833001, name='Legacy Corp', specialization='miner', cash=987654)
            session.add(legacy)
            await session.commit()
            old_state = (legacy.cash, legacy.level)

            await NextGameService.create_company(session, 551777, 'Тестовая корпорация')
            with pytest.raises(ValueError, match='конечное число'):
                await NextGameService.trade(session, 551777, 'energy', 'BUY', float('nan'))
            with pytest.raises(ValueError, match='4 знака'):
                await NextGameService.trade(session, 551777, 'energy', 'BUY', 0.00001)
            initial = await NextGameService.snapshot(session, 551777, now=now)
            assert initial['company']['cash'] == 10_000
            assert initial['treasury']['cash'] == 99_990_000
            retried = await NextGameService.create_company(session, 551777, 'Повторный запрос')
            assert retried['company']['name'] == 'Тестовая корпорация'
            assert (await NextGameService.snapshot(session, 551777, now=now))['treasury']['cash'] == 99_990_000
            await NextGameService.select_sector(session, 551777, 'resources')
            await NextGameService.select_branch(session, 551777, 'ore_mining')
            built = await NextGameService.build_facility(session, 551777, now=now)
            assert built['facility']['branch_id'] == 'ore_mining'

            early = await NextGameService.settle_company(session, 551777, now=now + timedelta(minutes=4))
            assert early['cycles_completed'] == 0
            blocked_snapshot = await NextGameService.snapshot(
                session, 551777, now=now + timedelta(minutes=4)
            )
            assert blocked_snapshot['facilities'][0]['status'] == 'blocked'
            assert 'Электроэнергия' in blocked_snapshot['facilities'][0]['blocked_reason']
            await NextGameService.trade(session, 551777, 'energy', 'BUY', 10, now=now)
            await NextGameService.trade(session, 551777, 'water', 'BUY', 5, now=now)
            produced = await NextGameService.settle_company(session, 551777, now=now + timedelta(minutes=5))
            assert produced['cycles_completed'] == 1
            sold = await NextGameService.trade(session, 551777, 'iron_ore', 'SELL', 12, now=now + timedelta(minutes=5))
            assert sold['success'] is True
            assert sold['cash_delta'] > 0

            snapshot = await NextGameService.snapshot(session, 551777, now=now + timedelta(minutes=5))
            assert snapshot['recent_activity'][0]['action'] == 'SELL'
            assert snapshot['recent_activity'][0]['cash_change'] == sold['cash_delta']
            inventory = {item['item_id']: item['quantity'] for item in snapshot['inventory']}
            assert 'iron_ore' not in inventory
            assert next(item for item in snapshot['market'] if item['item_id'] == 'iron_ore')['quantity'] == 0
            assert inventory['energy'] == 7
            assert inventory['water'] == 4
            assert snapshot['company']['xp'] == 200
            ledger = list((await session.scalars(
                select(NatNextGameLedger).where(NatNextGameLedger.company_id == snapshot['company']['id'])
            )).all())
            assert snapshot['treasury']['cash'] == pytest.approx(
                100_000_000 + sum(row.cash_treasury_delta for row in ledger),
                abs=0.01,
            )

            assert ledger
            assert sum(row.action == 'STARTUP_CAPITAL' for row in ledger) == 1
            assert all(round(row.cash_company_delta + row.cash_treasury_delta, 2) == 0 for row in ledger)
            assert (legacy.cash, legacy.level) == old_state
            with pytest.raises(ValueError, match='Недостаточно'):
                await NextGameService.trade(session, 551777, 'iron_ore', 'SELL', 1, now=now + timedelta(minutes=5))

        await engine.dispose()

    asyncio.run(check())


def test_bank_loan_uses_treasury_cash_and_repayment_returns_principal_plus_interest():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 551779, 'Нужен кредит')
            before = await NextGameService.snapshot(session, 551779, now=start)
            loan = await NextGameService.request_bank_loan(
                session, 551779, 5_000, now=start,
            )
            assert loan['loan']['principal'] == 5_000
            assert loan['loan']['repayment_amount'] == 5_050
            after_issue = await NextGameService.snapshot(session, 551779, now=start)
            assert after_issue['company']['cash'] == 15_000
            assert after_issue['treasury']['cash'] == before['treasury']['cash'] - 5_000
            assert after_issue['bank_loan']['status'] == 'ACTIVE'
            with pytest.raises(ValueError, match='активный кредит'):
                await NextGameService.request_bank_loan(session, 551779, 1_000, now=start)

            paid = await NextGameService.repay_bank_loan(
                session, 551779, now=start + timedelta(days=1),
            )
            assert paid['success'] is True
            assert paid['paid_amount'] == 5_050
            final = await NextGameService.snapshot(
                session, 551779, now=start + timedelta(days=1),
            )
            assert final['company']['cash'] == 9_950
            assert final['treasury']['cash'] == before['treasury']['cash'] + 50
            row = await session.scalar(select(NatNextGameLoan).where(
                NatNextGameLoan.company_id == final['company']['id']
            ))
            assert row.status == 'PAID'
            ledger = list((await session.scalars(
                select(NatNextGameLedger).where(NatNextGameLedger.company_id == final['company']['id'])
            )).all())
            assert all(round(r.cash_company_delta + r.cash_treasury_delta, 2) == 0 for r in ledger)
        await engine.dispose()

    asyncio.run(check())


def test_term_deposit_reserves_maturity_value_and_pays_interest_only_after_due_date():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 551780, 'Вкладчик')
            await NextGameService.trade(session, 551780, 'energy', 'BUY', 1)
            before = await NextGameService.snapshot(session, 551780, now=start)

            opened = await NextGameService.open_bank_deposit(
                session, 551780, 5_000, 1, now=start,
            )
            assert opened['deposit']['principal'] == 5_000
            assert opened['deposit']['interest'] == 12.5
            assert opened['deposit']['maturity_amount'] == 5_012.5
            after_open = await NextGameService.snapshot(session, 551780, now=start)
            assert after_open['company']['cash'] == 4_988
            assert after_open['treasury']['total_cash'] == before['treasury']['total_cash'] + 5_000
            assert after_open['treasury']['reserved_for_deposits'] == 5_012.5
            assert after_open['treasury']['cash'] == before['treasury']['cash'] - 12.5
            assert after_open['deposits'][0]['status'] == 'ACTIVE'

            with pytest.raises(ValueError):
                await NextGameService.withdraw_bank_deposit(
                    session, 551780, opened['deposit']['id'], now=start + timedelta(hours=23),
                )

            # Simulate a depleted free reserve: the protected deposit balance remains unavailable.
            treasury = await session.get(NatNextGameTreasury, 1)
            treasury.cash = 5_012.5
            depleted = await NextGameService.snapshot(session, 551780, now=start)
            assert depleted['treasury']['cash'] == 0
            assert depleted['bank_credit_limit'] == 0
            with pytest.raises(ValueError):
                await NextGameService.request_bank_loan(session, 551780, 1_000, now=start)
            with pytest.raises(ValueError):
                await NextGameService.trade(session, 551780, 'energy', 'SELL', 1, now=start)

            paid = await NextGameService.withdraw_bank_deposit(
                session, 551780, opened['deposit']['id'], now=start + timedelta(days=1),
            )
            assert paid['success'] is True
            assert paid['interest'] == 12.5
            final = await NextGameService.snapshot(
                session, 551780, now=start + timedelta(days=1),
            )
            assert final['company']['cash'] == 10_000.5
            assert final['treasury']['total_cash'] == 0
            assert final['treasury']['reserved_for_deposits'] == 0
            stored = await session.get(NatNextGameDeposit, opened['deposit']['id'])
            assert stored.status == 'WITHDRAWN'
            entries = list((await session.scalars(
                select(NatNextGameLedger).where(NatNextGameLedger.company_id == final['company']['id'])
            )).all())
            assert sum(row.action == 'BANK_DEPOSIT_OPEN' for row in entries) == 1
            assert sum(row.action == 'BANK_DEPOSIT_WITHDRAW' for row in entries) == 1
            assert all(round(row.cash_company_delta + row.cash_treasury_delta, 2) == 0 for row in entries)
        await engine.dispose()

    asyncio.run(check())


def test_active_deposits_remain_visible_after_more_than_twelve_closed_deposits():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 551781, 'Длинный вкладчик')
            current = start
            for _ in range(13):
                opened = await NextGameService.open_bank_deposit(
                    session, 551781, 1_000, 1, now=current,
                )
                await NextGameService.withdraw_bank_deposit(
                    session, 551781, opened['deposit']['id'],
                    now=current + timedelta(days=1),
                )
                current += timedelta(days=2)

            active = await NextGameService.open_bank_deposit(
                session, 551781, 1_000, 1, now=current,
            )
            snapshot = await NextGameService.snapshot(session, 551781, now=current)

            assert any(
                row['id'] == active['deposit']['id'] and row['status'] == 'ACTIVE'
                for row in snapshot['deposits']
            )
            assert sum(row['status'] == 'WITHDRAWN' for row in snapshot['deposits']) == 12
        await engine.dispose()

    asyncio.run(check())


def test_concurrent_deposits_cannot_spend_the_same_treasury_interest_reserve(tmp_path):
    async def check():
        database_path = (tmp_path / 'deposit-reserve-lock.db').as_posix()
        engine = create_async_engine(f'sqlite+aiosqlite:///{database_path}')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            await NextGameService.create_company(session, 551782, 'Первый вкладчик')
            await NextGameService.create_company(session, 551783, 'Второй вкладчик')
            treasury = await session.get(NatNextGameTreasury, 1)
            treasury.cash = 2.5
            await session.commit()

        async def try_open(owner_tg_id):
            async with sessions() as session:
                try:
                    await NextGameService.open_bank_deposit(
                        session, owner_tg_id, 1_000, 1,
                        now=datetime(2026, 10, 10, 12, 0),
                    )
                    await session.commit()
                    return 'opened'
                except ValueError:
                    await session.rollback()
                    return 'rejected'

        outcomes = await asyncio.gather(try_open(551782), try_open(551783))
        assert sorted(outcomes) == ['opened', 'rejected']
        await engine.dispose()

    asyncio.run(check())


def test_admin_map_commits_lazy_production_settlement(monkeypatch):
    async def check():
        from backend.natbirzha.api import next_game_routes

        class Session:
            committed = False

            async def commit(self):
                self.committed = True

        session = Session()

        async def lock(_session):
            assert _session is session

        async def scalar(_query):
            return None

        session.scalar = scalar
        monkeypatch.setattr(next_game_routes.NextGameMarketService, 'lock_orderbook', staticmethod(lock))

        async def snapshot(_session, owner_tg_id, *, section):
            assert _session is session
            assert owner_tg_id == 123456
            assert section == 'overview'
            return {'company': {'id': 1}}

        monkeypatch.setattr(
            next_game_routes.NextGameService, 'snapshot', staticmethod(snapshot)
        )
        result = await next_game_routes.get_map(
            admin=SimpleNamespace(tg_id=123456), session=session, section='overview'
        )
        assert result == {'company': {'id': 1}, 'recovery': {'requires_ack': False, 'was_triggered': False}}
        assert session.committed is True

    asyncio.run(check())


def test_economy_migration_upgrades_existing_preview_table_idempotently():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as connection:
            await connection.execute(text("""
                CREATE TABLE nat_next_game_companies (
                    id INTEGER PRIMARY KEY,
                    owner_tg_id BIGINT NOT NULL UNIQUE,
                    name VARCHAR(80) NOT NULL,
                    sector_id VARCHAR(48),
                    branch_path JSON NOT NULL DEFAULT '[]',
                    cash FLOAT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """))
            await connection.execute(text("""
                INSERT INTO nat_next_game_companies
                    (id, owner_tg_id, name, branch_path, cash, created_at, updated_at)
                VALUES (1, 77, 'Старая тестовая компания', '[]', 10000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """))
            await migrate_next_game_economy(connection)
            await migrate_next_game_economy(connection)
            await migrate_next_game_bank(connection)
            await migrate_next_game_bank(connection)
            await migrate_next_game_deposits(connection)
            await migrate_next_game_deposits(connection)
            await migrate_next_game_equity(connection)
            await migrate_next_game_equity(connection)
            await migrate_next_game_banking(connection)
            await migrate_next_game_banking(connection)
            await migrate_next_game_finance(connection)
            await migrate_next_game_finance(connection)
            columns = await connection.execute(text('PRAGMA table_info("nat_next_game_companies")'))
            column_names = {row[1] for row in columns.fetchall()}
            assert {'level', 'xp'} <= column_names
            state = await connection.execute(text(
                'SELECT level, xp FROM nat_next_game_companies WHERE owner_tg_id=77'
            ))
            assert state.one() == (1, 0)
            tables = await connection.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'nat_next_game_%'"
            ))
            assert {
                'nat_next_game_facilities', 'nat_next_game_inventory',
                'nat_next_game_treasury', 'nat_next_game_ledger', 'nat_next_game_loans',
                'nat_next_game_deposits',
                'nat_next_game_share_issues', 'nat_next_game_share_holdings',
                'nat_next_game_share_orders', 'nat_next_game_share_trades',
                'nat_next_game_dividends', 'nat_next_game_dividend_payments',
                'nat_next_game_bank_accounts', 'nat_next_game_bank_payments',
                'nat_next_game_corporate_loans',
                'nat_next_game_finance_contracts',
            } <= {row[0] for row in tables.fetchall()}
        await engine.dispose()

    asyncio.run(check())


def test_existing_preview_company_opening_cash_is_moved_from_the_new_treasury_once():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            session.add(NatNextGameCompany(
                owner_tg_id=551778, name='Предыдущий тест 2.0',
                branch_path=[], cash=10_000, level=1, xp=0,
            ))
            await session.commit()
            first = await NextGameService.snapshot(session, 551778)
            assert first['company']['cash'] == 10_000
            assert first['treasury']['cash'] == 99_990_000
            second = await NextGameService.snapshot(session, 551778)
            assert second['treasury']['cash'] == 99_990_000
            grants = list((await session.scalars(
                select(NatNextGameLedger).where(
                    NatNextGameLedger.company_id == first['company']['id'],
                    NatNextGameLedger.action == 'STARTUP_CAPITAL',
                )
            )).all())
            assert len(grants) == 1
            assert grants[0].cash_treasury_delta == -10_000
        await engine.dispose()

    asyncio.run(check())
