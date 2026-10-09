"""Database columns for rebirth valuation anchors."""

from sqlalchemy import text


async def migrate_rebirth_stock_anchor(conn) -> None:
    if conn.dialect.name == "sqlite":
        rows = await conn.execute(text('PRAGMA table_info("nat_stocks")'))
        columns = {row[1] for row in rows.fetchall()}
    else:
        rows = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name='nat_stocks'"
        ))
        columns = {row[0] for row in rows.fetchall()}
    if not columns:
        return
    for name in ("rebirth_valuation_anchor", "rebirth_base_valuation"):
        if name not in columns:
            await conn.execute(text(
                f'ALTER TABLE "nat_stocks" ADD COLUMN "{name}" FLOAT'
            ))


__all__ = ["migrate_rebirth_stock_anchor"]
