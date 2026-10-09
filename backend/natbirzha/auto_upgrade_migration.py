"""Add the opt-in, stage-nine auto-upgrade preference to existing companies."""

from sqlalchemy import text


async def migrate_auto_upgrade_to_nine(conn) -> None:
    if conn.dialect.name == "sqlite":
        rows = await conn.execute(text('PRAGMA table_info("nat_companies")'))
        columns = {row[1] for row in rows.fetchall()}
    else:
        rows = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name='nat_companies'
        """))
        columns = {row[0] for row in rows.fetchall()}
    if columns and "auto_upgrade_to_nine_enabled" not in columns:
        await conn.execute(text(
            'ALTER TABLE "nat_companies" ADD COLUMN "auto_upgrade_to_nine_enabled" '
            'BOOLEAN NOT NULL DEFAULT FALSE'
        ))


__all__ = ["migrate_auto_upgrade_to_nine"]
