"""Expand the private 2.0 company and add its isolated market tables."""

from sqlalchemy import text

from backend.natbirzha.models.next_game import (
    NatNextGameFacility,
    NatNextGameInventory,
    NatNextGameLedger,
    NatNextGameTreasury,
)


async def migrate_next_game_economy(conn) -> None:
    if conn.dialect.name == "sqlite":
        rows = await conn.execute(text('PRAGMA table_info("nat_next_game_companies")'))
        columns = {row[1] for row in rows.fetchall()}
    else:
        rows = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name='nat_next_game_companies'
        """))
        columns = {row[0] for row in rows.fetchall()}

    if not columns:
        raise RuntimeError("nat_next_game_companies must exist before its economy migration")

    for name, default in (("level", 1), ("xp", 0)):
        if name not in columns:
            await conn.execute(text(
                f'ALTER TABLE "nat_next_game_companies" ADD COLUMN "{name}" '
                f"INTEGER NOT NULL DEFAULT {default}"
            ))

    for model in (NatNextGameFacility, NatNextGameInventory, NatNextGameTreasury, NatNextGameLedger):
        await conn.run_sync(lambda sync_conn, table=model.__table__: table.create(sync_conn, checkfirst=True))


async def migrate_next_game_bank(conn) -> None:
    from backend.natbirzha.models.next_game import NatNextGameLoan

    await conn.run_sync(
        lambda sync_conn: NatNextGameLoan.__table__.create(sync_conn, checkfirst=True)
    )


__all__ = ["migrate_next_game_bank", "migrate_next_game_economy"]
