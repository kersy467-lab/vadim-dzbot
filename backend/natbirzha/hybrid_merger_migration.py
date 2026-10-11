"""Create active hybrid-merger state on databases which already have V2 businesses."""

from sqlalchemy import inspect, text


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


async def migrate_hybrid_progress(conn) -> None:
    """Restore active hybrids to the average progression of their source plants."""
    has_tables = await conn.run_sync(
        lambda sync_conn: all(
            inspect(sync_conn).has_table(table_name)
            for table_name in ("nat_businesses", "nat_hybrid_mergers")
        )
    )
    if not has_tables:
        return

    rows = await conn.execute(text("""
        SELECT business.id, business.stage, merger.source_a_stage, merger.source_b_stage
        FROM nat_businesses AS business
        JOIN nat_hybrid_mergers AS merger
          ON merger.hybrid_business_id = business.id
        WHERE merger.status = 'ACTIVE'
          AND merger.hybrid_business_id IS NOT NULL
    """))
    for row in rows.mappings():
        preserved_stage = min(
            50,
            max(1, (int(row["source_a_stage"]) + int(row["source_b_stage"]) + 1) // 2),
        )
        target_stage = max(int(row["stage"]), preserved_stage)
        if target_stage == int(row["stage"]):
            continue
        await conn.execute(text("""
            UPDATE nat_businesses
            SET stage = :stage, updated_at = CURRENT_TIMESTAMP
            WHERE id = :business_id
        """), {"stage": target_stage, "business_id": row["id"]})


__all__ = ["migrate_hybrid_mergers", "migrate_hybrid_progress"]
