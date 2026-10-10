"""Create the isolated NATBIRZHA 2.0 IPO and dividend tables."""

from sqlalchemy import text

from backend.natbirzha.models.next_game_equity import (
    NatNextGameDividend,
    NatNextGameDividendPayment,
    NatNextGameShareHolding,
    NatNextGameShareIssue,
    NatNextGameShareOrder,
    NatNextGameShareTrade,
)


async def migrate_next_game_equity(conn) -> None:
    if not await _table_exists(conn, "nat_next_game_companies"):
        raise RuntimeError("nat_next_game_companies must exist before its equity migration")
    models = (
        NatNextGameShareIssue,
        NatNextGameShareHolding,
        NatNextGameShareOrder,
        NatNextGameShareTrade,
        NatNextGameDividend,
        NatNextGameDividendPayment,
    )
    for model in models:
        if await _table_exists(conn, model.__tablename__):
            continue
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


__all__ = ["migrate_next_game_equity"]
