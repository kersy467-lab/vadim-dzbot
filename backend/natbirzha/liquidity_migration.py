"""Create the persisted rolling liquidity snapshot table on existing databases."""

from sqlalchemy import inspect


async def migrate_liquidity_snapshots(conn) -> None:
    has_companies = await conn.run_sync(
        lambda sync_conn: inspect(sync_conn).has_table("nat_companies")
    )
    if not has_companies:
        return

    import backend.natbirzha.models  # noqa: F401 - register the table
    from backend.db.models import Base

    await conn.run_sync(
        lambda sync_conn: Base.metadata.tables["nat_liquidity_snapshots"].create(
            sync_conn, checkfirst=True
        )
    )


__all__ = ["migrate_liquidity_snapshots"]
