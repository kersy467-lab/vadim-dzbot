"""Add case-source and visible-level metadata to existing 2.0 managers."""

from sqlalchemy import text


async def migrate_next_game_employees(conn) -> None:
    from backend.natbirzha.migrations import _add_columns, _table_exists

    if not await _table_exists(conn, "nat_next_game_managers"):
        return
    await _add_columns(conn, "nat_next_game_managers", {
        "source": "VARCHAR(16) NOT NULL DEFAULT 'milestone'",
        "level": "INTEGER NOT NULL DEFAULT 1",
    })
    await conn.execute(text("""
        UPDATE nat_next_game_managers
        SET level=reward_level
        WHERE source='milestone' AND reward_level BETWEEN 1 AND 50
    """))


__all__ = ["migrate_next_game_employees"]
