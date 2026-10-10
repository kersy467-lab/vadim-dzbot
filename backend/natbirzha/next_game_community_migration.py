"""New isolated tables; existing games and accounts are not reset."""
async def migrate_next_game_community(conn):
    from backend.natbirzha.models.next_game_community import (
        NatNextGameProfile, NatNextGameHelpRequest, NatNextGameTransfer, NatNextGameAdminAudit,
    )
    for model in (NatNextGameProfile, NatNextGameHelpRequest, NatNextGameTransfer, NatNextGameAdminAudit):
        await conn.run_sync(lambda sync, table=model.__table__: table.create(sync, checkfirst=True))
