"""Create company banking accounts and settlement history for NATBIRZHA 2.0."""

from sqlalchemy import text

from backend.natbirzha.models.next_game_banking import (
    NatNextGameBankAccount,
    NatNextGameBankPayment,
    NatNextGameCorporateLoan,
)


async def migrate_next_game_banking(conn) -> None:
    if not await _table_exists(conn, "nat_next_game_companies"):
        raise RuntimeError("nat_next_game_companies must exist before banking migration")
    for model in (NatNextGameBankAccount, NatNextGameBankPayment, NatNextGameCorporateLoan):
        await conn.run_sync(
            lambda sync_conn, table=model.__table__: table.create(sync_conn, checkfirst=True)
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


__all__ = ["migrate_next_game_banking"]
