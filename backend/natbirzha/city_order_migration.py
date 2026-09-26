"""Schema migration for the shared city-order cycle and settlement ledger."""

from sqlalchemy import inspect


async def migrate_city_orders(conn) -> None:
    exists = await conn.run_sync(
        lambda sync_conn: inspect(sync_conn).has_table("nat_companies")
    )
    if not exists:
        return
    import backend.natbirzha.models  # noqa: F401 - register the tables
    from backend.db.models import Base

    table_names = (
        "nat_city_order_cycle_states", "nat_city_orders", "nat_city_order_deliveries",
    )
    for name in table_names:
        await conn.run_sync(
            lambda sync_conn, table_name=name: Base.metadata.tables[table_name].create(
                sync_conn, checkfirst=True
            )
        )


__all__ = ["migrate_city_orders"]
