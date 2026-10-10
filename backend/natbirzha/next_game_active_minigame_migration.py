"""Persist wheel state and server-scored output multipliers for active production."""

from sqlalchemy import text


async def migrate_next_game_active_minigame(conn) -> None:
    from backend.natbirzha.migrations import _add_columns

    await _add_columns(conn, "nat_next_game_active_sessions", {
        "skill_charge": "INTEGER NOT NULL DEFAULT 0",
        "hit_streak": "INTEGER NOT NULL DEFAULT 0",
        "wheel_angle": "FLOAT NOT NULL DEFAULT 0",
        "wheel_direction": "INTEGER NOT NULL DEFAULT 1",
        "target_angle": "FLOAT NOT NULL DEFAULT 180",
        "last_skill_tap_at": "TIMESTAMP NULL",
    })
    await _add_columns(conn, "nat_next_game_active_intervals", {
        # Existing sessions used a fixed 1.5x activity bonus; keep their history intact.
        "output_multiplier": "FLOAT NOT NULL DEFAULT 1.5",
    })

    if await _table_exists(conn, "nat_next_game_active_intervals"):
        await conn.execute(text(
            "UPDATE nat_next_game_active_intervals SET output_multiplier=1.5 "
            "WHERE output_multiplier IS NULL OR output_multiplier < 1"
        ))


async def _table_exists(conn, table: str) -> bool:
    if conn.dialect.name == "sqlite":
        result = await conn.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"), {"name": table})
    else:
        result = await conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=current_schema() AND table_name=:name"
        ), {"name": table})
    return result.first() is not None


__all__ = ["migrate_next_game_active_minigame"]
