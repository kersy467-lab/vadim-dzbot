"""Create active hybrid-merger state on databases which already have V2 businesses."""

from sqlalchemy import inspect


async def migrate_hybrid_mergers(conn) -> None:
    has_businesses = await conn.run_sync(
        lambda sync_conn: inspect(sync_conn).has_table("nat_businesses")
    )
    if not has_businesses:
        return

    import backend.natbirzha.models  # noqa: F401 - register the table and foreign keys
    from backend.db.models import Base

    await conn.run_sync(
        lambda sync_conn: Base.metadata.tables["nat_hybrid_mergers"].create(
            sync_conn, checkfirst=True
        )
    )


__all__ = ["migrate_hybrid_mergers"]
