"""Persist continuous facility upgrades, 64-bit company progression and managers."""

from sqlalchemy import text


async def migrate_next_game_continuous_progression(conn) -> None:
    from backend.natbirzha.migrations import _add_columns, _table_exists
    from backend.natbirzha.models.next_game_managers import NatNextGameManager

    if not await _table_exists(conn, "nat_next_game_companies"):
        return

    await _add_columns(conn, "nat_next_game_facilities", {
        "upgrade_target_level": "INTEGER",
        "upgrade_finishes_at": "TIMESTAMP",
        "upgrade_reserved_cash": "FLOAT NOT NULL DEFAULT 0",
    })
    if conn.dialect.name != "sqlite":
        for column in ("level", "xp"):
            await conn.execute(text(
                f"ALTER TABLE nat_next_game_companies ALTER COLUMN {column} "
                f"TYPE BIGINT USING {column}::bigint"
            ))

    await conn.run_sync(
        lambda sync_conn: NatNextGameManager.__table__.create(sync_conn, checkfirst=True)
    )


__all__ = ["migrate_next_game_continuous_progression"]
