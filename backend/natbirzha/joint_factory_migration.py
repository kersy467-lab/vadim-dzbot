"""Create persistent joint-factory state on an existing NATBIRZHA database."""

from sqlalchemy import inspect


async def migrate_joint_factories(conn) -> None:
    has_companies = await conn.run_sync(
        lambda sync_conn: inspect(sync_conn).has_table("nat_companies")
    )
    if not has_companies:
        return

    import backend.natbirzha.models  # noqa: F401 - register model metadata
    from backend.db.models import Base

    for table_name in (
        "nat_joint_factories",
        "nat_joint_factory_proposals",
        "nat_joint_factory_settlements",
    ):
        await conn.run_sync(
            lambda sync_conn, name=table_name: Base.metadata.tables[name].create(
                sync_conn, checkfirst=True
            )
        )


__all__ = ["migrate_joint_factories"]
