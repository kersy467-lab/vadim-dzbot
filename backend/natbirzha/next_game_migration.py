"""Create the isolated preview-game table without altering legacy companies."""


async def migrate_next_game_sandbox(conn) -> None:
    from backend.natbirzha.models.next_game import NatNextGameCompany
    await conn.run_sync(
        lambda sync_conn: NatNextGameCompany.__table__.create(sync_conn, checkfirst=True)
    )


__all__ = ["migrate_next_game_sandbox"]
