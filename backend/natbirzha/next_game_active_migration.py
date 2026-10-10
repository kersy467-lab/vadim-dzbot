"""Add activity-session and qualified-interval tables for 2.0 production."""


async def migrate_next_game_active(conn):
    from backend.natbirzha.models.next_game_active import (
        NatNextGameActiveSession,
        NatNextGameActiveInterval,
    )

    for model in (NatNextGameActiveSession, NatNextGameActiveInterval):
        await conn.run_sync(lambda sync, table=model.__table__: table.create(sync, checkfirst=True))


__all__ = ["migrate_next_game_active"]
