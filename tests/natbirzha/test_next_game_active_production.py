from datetime import datetime, timedelta
import asyncio
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameLedger
from backend.natbirzha.models.next_game_active import NatNextGameActiveInterval, NatNextGameActiveSession
from backend.natbirzha.next_game_catalog import find_next_game_branch
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.active_production_scene_catalog import get_active_production_scene_catalog
from backend.natbirzha.services.next_game_active_production_service import (
    NextGameActiveProductionService, active_cycle_multiplier, output_with_active_bonus,
)
from backend.natbirzha.services.active_production_minigame import (
    WHEEL_SPEED_DEGREES_PER_SECOND, advance_wheel, server_epoch_millis,
)


def test_active_multiplier_counts_only_clipped_cycle_overlap_and_caps_at_five_x():
    start = datetime(2026, 10, 10, 12, 0)
    end = start + timedelta(seconds=300)

    factor, active_seconds = active_cycle_multiplier(start, end, [
        (start - timedelta(seconds=20), start + timedelta(seconds=120)),
        (start + timedelta(seconds=400), start + timedelta(seconds=500)),
    ])

    assert factor == 1.2
    assert active_seconds == 120

    capped, capped_seconds = active_cycle_multiplier(start, end, [
        (start, end + timedelta(seconds=100)),
    ])
    assert capped == 1.5
    assert capped_seconds == 300


def test_active_multiplier_time_weights_server_scored_segments_and_caps_at_five_x():
    start = datetime(2026, 10, 10, 12, 0)
    end = start + timedelta(seconds=300)

    weighted, active_seconds = active_cycle_multiplier(start, end, [
        (start, start + timedelta(seconds=100), 2.0),
        (start + timedelta(seconds=100), start + timedelta(seconds=200), 5.0),
    ])
    assert weighted == 2.66666667
    assert active_seconds == 200

    capped, _ = active_cycle_multiplier(start, end, [(start, end, 99.0)])
    assert capped == 5.0


def test_active_multiplier_merges_overlapping_intervals_and_ignores_invalid_cycles():
    start = datetime(2026, 10, 10, 12, 0)
    end = start + timedelta(seconds=300)
    factor, active_seconds = active_cycle_multiplier(start, end, [
        (start, start + timedelta(seconds=100)),
        (start + timedelta(seconds=50), start + timedelta(seconds=150)),
    ])

    assert factor == 1.25
    assert active_seconds == 150
    assert active_cycle_multiplier(end, start, [(start, end)]) == (1.0, 0)
    assert active_cycle_multiplier(start, end, []) == (1.0, 0)


def test_active_output_clips_bonus_to_capacity_without_blocking_baseline_output():
    assert output_with_active_bonus(10, 1.5, 100, 85, 5) == (10, 0)
    assert output_with_active_bonus(10, 1.5, 100, 80, 5) == (15, 5)
    assert output_with_active_bonus(10, 1.3333, 100, 80, 4.5) == (13.333, 3.333)


def test_active_scene_catalog_covers_all_current_branch_ids():
    catalog = get_active_production_scene_catalog()
    assert len(catalog) == 205
    assert catalog["ore_mining"]["scene_family"] == "resources"
    assert catalog["logistics"]["scene_family"] == "infrastructure"
    assert (catalog["ore_mining"]["visual_pickup"], catalog["ore_mining"]["delivery_marker"]) == (
        "Железная руда", "Вагонетка",
    )
    assert (catalog["logistics"]["workstation"], catalog["logistics"]["delivery_marker"]) == (
        "Склад", "Магазин",
    )
    assert (catalog["ore_mining"]["visual_pickup"], catalog["ore_mining"]["delivery_marker"]) == (
        "Железная руда", "Вагонетка",
    )
    assert (catalog["logistics"]["workstation"], catalog["logistics"]["delivery_marker"]) == (
        "Склад", "Магазин",
    )
    assert all(scene["visual_pickup"] and scene["workstation"] and scene["delivery_marker"]
               and scene["vehicle"] for scene in catalog.values())


def test_session_tokens_rotate_and_duplicate_pulses_cannot_add_more_active_time(monkeypatch):
    async def check():
        monkeypatch.setenv('NEXT_GAME_ACTIVE_PRODUCTION_ENABLED', 'true')
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 772002, 'Активная компания')
            await NextGameService.select_sector(session, 772002, 'resources')
            await NextGameService.select_branch(session, 772002, 'ore_mining')
            await NextGameService.build_facility(session, 772002, now=start)
            started = await NextGameActiveProductionService.start(
                session, 772002, 'ore_mining', now=start,
            )
            row = await session.get(NatNextGameActiveSession, started['session_id'])
            assert row.session_token_hash != started['session_token']

            pulse = await NextGameActiveProductionService.pulse(
                session, 772002, started['session_id'], started['session_token'],
                1, 'pickup', 1, now=start + timedelta(seconds=15),
            )
            retry = await NextGameActiveProductionService.pulse(
                session, 772002, started['session_id'], started['session_token'],
                1, 'pickup', 1, now=start + timedelta(seconds=20),
            )
            assert pulse['active'] is True
            assert retry['duplicate'] is True

            fake_move = await NextGameActiveProductionService.pulse(
                session, 772002, started['session_id'], started['session_token'],
                2, 'move', 2, now=start + timedelta(seconds=25),
            )
            assert fake_move['active'] is True
            assert row.last_interaction_at == start + timedelta(seconds=15)
            assert row.last_user_input_counter == 1
            processed_order = await NextGameActiveProductionService.pulse(
                session, 772002, started['session_id'], started['session_token'],
                3, 'interact', 2, now=start + timedelta(seconds=30),
            )
            assert processed_order['active'] is True
            assert row.last_interaction_at == start + timedelta(seconds=30)
            delivered_order = await NextGameActiveProductionService.pulse(
                session, 772002, started['session_id'], started['session_token'],
                4, 'deliver', 3, now=start + timedelta(seconds=45),
            )
            assert delivered_order['active'] is True
            assert row.last_interaction_at == start + timedelta(seconds=45)

            await NextGameActiveProductionService.finish(
                session, 772002, started['session_id'], started['session_token'],
                status='PAUSED', now=start + timedelta(seconds=45),
            )
            factor, seconds = await active_cycle_multiplier_from_db(
                session, row.company_id, start, start + timedelta(seconds=300),
            )
            assert factor == 1.0
            assert seconds == 45
            await NextGameActiveProductionService.finish(
                session, 772002, started['session_id'], started['session_token'],
                status='STOPPED', now=start + timedelta(seconds=31),
            )
            assert row.status == 'STOPPED'
        await engine.dispose()

    asyncio.run(check())


def test_timing_taps_are_server_scored_rate_limited_and_saved_as_output_factor(monkeypatch):
    async def check():
        monkeypatch.setenv('NEXT_GAME_ACTIVE_PRODUCTION_ENABLED', 'true')
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        start = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 772003, 'Ритм-цех')
            await NextGameService.select_sector(session, 772003, 'resources')
            await NextGameService.select_branch(session, 772003, 'ore_mining')
            await NextGameService.build_facility(session, 772003, now=start)
            started = await NextGameActiveProductionService.start(
                session, 772003, 'ore_mining', now=start,
            )
            row = await session.get(NatNextGameActiveSession, started['session_id'])
            timing = started['timing']
            from backend.natbirzha.services.active_production_minigame import advance_wheel
            pointer = advance_wheel(
                timing['pointer_angle'], timing['direction'], timing['speed'], .1,
            )
            # The chosen tap is a timestamped server event; clients cannot submit a claimed grade.
            row.target_bars_json = json.dumps([{
                'id': 'hit-me', 'angle': pointer, 'kind': 'gold',
                'visible_at_ms': server_epoch_millis(start),
            }])
            first = await NextGameActiveProductionService.pulse(
                session, 772003, started['session_id'], started['session_token'],
                1, 'tap', 1, now=start + timedelta(seconds=.1),
            )
            assert first['tap_result'] == 'gold'
            assert first['timing']['charge'] == 2
            assert first['timing']['multiplier'] == 1.5
            assert first['timing']['direction'] == -timing['direction']
            assert 'hit-me' not in {bar['id'] for bar in first['timing']['target_bars']}

            retry = await NextGameActiveProductionService.pulse(
                session, 772003, started['session_id'], started['session_token'],
                2, 'tap', 2, now=start + timedelta(seconds=.2),
            )
            assert retry['tap_result'] == 'too_soon'
            assert retry['timing']['charge'] == 2

            heartbeat = await NextGameActiveProductionService.pulse(
                session, 772003, started['session_id'], started['session_token'],
                3, 'idle', 2, now=start + timedelta(seconds=15.1),
            )
            assert heartbeat['timing']['charge'] == 2
            intervals = list((await session.scalars(select(NatNextGameActiveInterval).where(
                NatNextGameActiveInterval.session_id == row.id,
            ))).all())
            assert intervals[-1].output_multiplier == pytest.approx(1.5)
            assert intervals[-1].start_at == start + timedelta(seconds=.2)
        await engine.dispose()

    asyncio.run(check())


def test_tap_is_scored_at_the_actual_client_press_and_hit_bar_disappears(monkeypatch):
    async def check():
        monkeypatch.setenv('NEXT_GAME_ACTIVE_PRODUCTION_ENABLED', 'true')
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        start = datetime(2026, 10, 10, 12, 0)
        pressed_at = start + timedelta(seconds=.2)
        received_at = start + timedelta(seconds=.5)
        async with sessions() as session:
            await NextGameService.create_company(session, 772004, 'Точный удар')
            await NextGameService.select_sector(session, 772004, 'resources')
            await NextGameService.select_branch(session, 772004, 'ore_mining')
            await NextGameService.build_facility(session, 772004, now=start)
            started = await NextGameActiveProductionService.start(
                session, 772004, 'ore_mining', now=start,
            )
            row = await session.get(NatNextGameActiveSession, started['session_id'])
            direction = row.wheel_direction
            initial_angle = row.wheel_angle
            hit_angle = advance_wheel(
                initial_angle, direction, WHEEL_SPEED_DEGREES_PER_SECOND, .2,
            )
            row.target_bars_json = json.dumps([{
                'id': 'latency-safe-hit', 'angle': hit_angle, 'kind': 'gold',
                'visible_at_ms': server_epoch_millis(start),
            }])

            result = await NextGameActiveProductionService.pulse(
                session, 772004, started['session_id'], started['session_token'],
                1, 'tap', 1, tap_at_ms=server_epoch_millis(pressed_at), now=received_at,
            )

            assert result['tap_result'] == 'gold'
            assert result['timing']['charge'] == 2
            assert result['timing']['direction'] == -direction
            assert 'latency-safe-hit' not in {bar['id'] for bar in result['timing']['target_bars']}
            expected_current_angle = advance_wheel(
                hit_angle, -direction, WHEEL_SPEED_DEGREES_PER_SECOND, .3,
            )
            assert result['timing']['pointer_angle'] == pytest.approx(expected_current_angle)
            assert row.last_skill_tap_at == pressed_at
            assert len(result['timing']['target_bars']) == 1
            assert result['timing']['target_bars'][0]['visible_at_ms'] > server_epoch_millis(received_at)

        await engine.dispose()

    asyncio.run(check())


async def active_cycle_multiplier_from_db(session, company_id, cycle_start, cycle_end):
    from backend.natbirzha.services.next_game_active_time import active_multiplier_for_cycle
    return await active_multiplier_for_cycle(session, company_id, cycle_start, cycle_end)


def test_settlement_applies_only_confirmed_active_time_and_does_not_pay_for_scene_actions(monkeypatch):
    async def check():
        monkeypatch.setenv('NEXT_GAME_ACTIVE_PRODUCTION_ENABLED', 'true')
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        start = datetime(2026, 10, 10, 12, 0)
        async with sessions() as session:
            await NextGameService.create_company(session, 772001, 'Игровой тест')
            await NextGameService.select_sector(session, 772001, 'resources')
            await NextGameService.select_branch(session, 772001, 'ore_mining')
            built = await NextGameService.build_facility(session, 772001, now=start)
            company_id = built['company']['id']
            facility = built['facility']
            end = start + timedelta(seconds=300)
            operating_cost = find_next_game_branch('ore_mining')['factory']['operating_cost']
            await NextGameService.trade(session, 772001, 'energy', 'BUY', 10, now=start)
            await NextGameService.trade(session, 772001, 'water', 'BUY', 5, now=start)
            session.add(NatNextGameActiveSession(
                id='active-test-session', company_id=company_id, owner_tg_id=772001,
                sector_id='resources', selected_branch_id='ore_mining', session_token_hash='x' * 64,
                status='STOPPED', started_at=start, last_ping_at=start,
                last_interaction_at=start, expires_at=end,
            ))
            await session.flush()
            session.add(NatNextGameActiveInterval(
                session_id='active-test-session', company_id=company_id, pulse_seq=1,
                start_at=start, end_at=start + timedelta(seconds=90), reason='heartbeat',
                output_multiplier=5.0,
            ))
            await session.flush()
            cash_before = (await NextGameService.snapshot(session, 772001, now=start))['company']['cash']

            result = await NextGameService.settle_company(session, 772001, now=end)
            inventory = await NextGameService._inventory_row(session, company_id, 'iron_ore')
            ledger = list((await session.scalars(select(NatNextGameLedger).where(
                NatNextGameLedger.company_id == company_id,
                NatNextGameLedger.action == 'PRODUCTION_OUTPUT',
            ))).all())

            assert result['cycles_completed'] == 1
            assert inventory.quantity == pytest.approx(12 * 2.2)
            assert (await NextGameService._owned_company(session, 772001)).cash == cash_before - operating_cost
            assert len(ledger) == 1
            assert ledger[0].metadata_json['active_production_multiplier'] == pytest.approx(2.2)
            assert ledger[0].metadata_json['active_seconds'] == 90
            assert ledger[0].metadata_json['bonus_output'] == pytest.approx(14.4)
            assert not any(row.action in {'ACTIVE_GAME_REWARD', 'GAME_DELIVERY'} for row in (
                await session.scalars(select(NatNextGameLedger).where(
                    NatNextGameLedger.company_id == company_id,
                ))
            ).all())

        await engine.dispose()

    asyncio.run(check())
