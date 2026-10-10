"""Persist the target bars used by the Pick the Lock active-production game."""


async def migrate_next_game_active_targets(conn) -> None:
    from backend.natbirzha.migrations import _add_columns

    await _add_columns(conn, "nat_next_game_active_sessions", {
        "target_bars_json": "TEXT NOT NULL DEFAULT '[]'",
    })


__all__ = ["migrate_next_game_active_targets"]
