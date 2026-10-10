"""Add the isolated NATBIRZHA 2.0 term-deposit table."""

from sqlalchemy import text

from backend.natbirzha.models.next_game import NatNextGameDeposit


async def migrate_next_game_deposits(conn) -> None:
    if not await _table_exists(conn, "nat_next_game_companies"):
        raise RuntimeError("nat_next_game_companies must exist before its deposit migration")
    if await _table_exists(conn, NatNextGameDeposit.__tablename__):
        return
    await conn.run_sync(
        lambda sync_conn: NatNextGameDeposit.__table__.create(sync_conn, checkfirst=True)
    )


async def _table_exists(conn, table_name: str) -> bool:
    if conn.dialect.name == "sqlite":
        result = await conn.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:table_name"
        ), {"table_name": table_name})
    else:
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema=current_schema() AND table_name=:table_name
        """), {"table_name": table_name})
    return result.first() is not None


__all__ = ["migrate_next_game_deposits"]
