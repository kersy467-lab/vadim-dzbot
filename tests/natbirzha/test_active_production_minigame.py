from datetime import datetime, timedelta
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.services.active_production_minigame import (
    MAX_OUTPUT_MULTIPLIER,
    advance_wheel,
    apply_tap_result,
    average_interval_multiplier,
    grade_tap,
    multiplier_for_charge,
)
from backend.natbirzha.next_game_active_minigame_migration import migrate_next_game_active_minigame


def test_wheel_timing_grades_gold_blue_and_miss_zones():
    assert grade_tap(8, 0) == "gold"
    assert grade_tap(188, 0) == "blue"
    assert grade_tap(100, 0) == "miss"
    assert grade_tap(359, 350) == "gold"


def test_skill_charge_builds_to_five_x_and_misses_lower_it_gradually():
    charge, streak = apply_tap_result(0, 0, "gold")
    assert (charge, streak) == (2, 1)
    charge, streak = apply_tap_result(charge, streak, "blue")
    assert (charge, streak) == (3, 2)
    assert multiplier_for_charge(charge) == 1.75

    charge, streak = apply_tap_result(15, 10, "gold")
    assert (charge, streak) == (16, 11)
    assert multiplier_for_charge(charge) == MAX_OUTPUT_MULTIPLIER == 5
    assert apply_tap_result(1, 3, "miss") == (0, 0)


def test_wheel_advance_and_bonus_decay_are_time_based():
    assert advance_wheel(350, 1, 120, 0.25) == 20
    assert advance_wheel(10, -1, 120, 0.25) == 340

    start = datetime(2026, 10, 11, 12, 0)
    end = start + timedelta(seconds=30)
    assert average_interval_multiplier(start, end, 16, start) == 3.66666667
    assert average_interval_multiplier(start, end, 8, start) == 2.33333333


def test_minigame_migration_adds_session_state_and_preserves_old_interval_bonus():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE nat_next_game_active_sessions (id VARCHAR(36) PRIMARY KEY)"))
            await conn.execute(text("""
                CREATE TABLE nat_next_game_active_intervals (
                    id INTEGER PRIMARY KEY, session_id VARCHAR(36), company_id INTEGER,
                    pulse_seq INTEGER, start_at TIMESTAMP, end_at TIMESTAMP, reason VARCHAR(24)
                )
            """))
            await conn.execute(text("""
                INSERT INTO nat_next_game_active_intervals
                    (id, session_id, company_id, pulse_seq, start_at, end_at, reason)
                VALUES (1, 'old', 9, 1, '2026-10-11 12:00:00', '2026-10-11 12:00:15', 'heartbeat')
            """))

            await migrate_next_game_active_minigame(conn)
            await migrate_next_game_active_minigame(conn)
            row = (await conn.execute(text(
                "SELECT output_multiplier FROM nat_next_game_active_intervals WHERE id=1"
            ))).one()
            assert row[0] == 1.5
            columns = (await conn.execute(text("PRAGMA table_info('nat_next_game_active_sessions')"))).all()
            assert {column[1] for column in columns} >= {
                "skill_charge", "hit_streak", "wheel_angle", "wheel_direction",
                "target_angle", "last_skill_tap_at",
            }
        await engine.dispose()

    asyncio.run(check())
