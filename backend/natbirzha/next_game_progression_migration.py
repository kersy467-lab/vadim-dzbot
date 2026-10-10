"""Create the isolated source-consuming merger audit table."""
async def migrate_next_game_progression(conn):
    from backend.natbirzha.models.next_game_progression import NatNextGameMerger
    await conn.run_sync(lambda sync: NatNextGameMerger.__table__.create(sync, checkfirst=True))
