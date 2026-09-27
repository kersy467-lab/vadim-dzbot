"""Restore database from JSON backup into any PostgreSQL database.
Usage:
    python scripts/restore_neon_db.py [NEW_DATABASE_URL] [--file path_to_backup.json]
"""

import asyncio
import os
import sys
import json
from datetime import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from backend.db.models import Base
import backend.natbirzha.models  # Register all models


async def restore_database(target_url: str, backup_file: str):
    if not os.path.exists(backup_file):
        print(f"Error: Backup file {backup_file} not found!")
        return False

    print(f"Loading backup data from {backup_file}...")
    with open(backup_file, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    meta = backup_data.get("metadata", {})
    tables_data = backup_data.get("tables", {})
    print(f"Backup created at: {meta.get('created_at')}")
    print(f"Total tables in backup: {len(tables_data)}")

    # Ensure target_url uses asyncpg driver
    clean_url = target_url
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif clean_url.startswith("postgresql://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"Connecting to target database...")
    engine = create_async_engine(clean_url, echo=False)

    # 1. Create all schema tables
    print("Creating schema tables in target database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    inserted_total = 0
    non_empty_tables = 0

    async with sessions() as session:
        # Disable triggers & foreign keys during restore
        await session.execute(text("SET session_replication_role = 'replica';"))

        # Order tables topologically
        ordered_tables = []
        for t in Base.metadata.sorted_tables:
            if t.name in tables_data:
                ordered_tables.append(t.name)
        for t in tables_data:
            if t not in ordered_tables:
                ordered_tables.append(t)

        for tbl in ordered_tables:
            tbl_info = tables_data[tbl]
            rows = tbl_info.get("rows", [])
            cols = tbl_info.get("columns", [])
            if not rows or not cols:
                continue

            print(f"Restoring table '{tbl}' ({len(rows)} rows)...")
            col_list = ", ".join(f'"{c}"' for c in cols)
            param_list = ", ".join(f":{c}" for c in cols)
            stmt = text(f'INSERT INTO "{tbl}" ({col_list}) VALUES ({param_list})')

            # Batch insert in chunks of 500
            chunk_size = 500
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i:i + chunk_size]
                # Cast JSON fields back to string/dict if needed
                await session.execute(stmt, chunk)

            inserted_total += len(rows)
            non_empty_tables += 1

        # Reset sequences to max(id)
        print("Resetting primary key sequences...")
        seq_res = await session.execute(text("""
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
        """))
        for seq_row in seq_res.fetchall():
            seq_name = seq_row[0]
            parts = seq_name.split("_")
            if len(parts) >= 2:
                tbl_guess = "_".join(parts[:-2]) if parts[-1] == "seq" else parts[0]
                col_guess = parts[-2] if parts[-1] == "seq" else "id"
                if tbl_guess in tables_data:
                    try:
                        await session.execute(text(f"""
                            SELECT setval('{seq_name}', COALESCE((SELECT MAX("{col_guess}") FROM "{tbl_guess}"), 1), true)
                        """))
                    except Exception:
                        pass

        await session.execute(text("SET session_replication_role = 'origin';"))
        await session.commit()

    await engine.dispose()
    print("\n" + "=" * 60)
    print("RESTORE COMPLETED SUCCESSFULLY!")
    print(f"Total tables restored: {non_empty_tables}")
    print(f"Total rows restored:   {inserted_total}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    from backend.config import settings
    target = None
    backup = os.path.join("data", "backups", "neon_backup_latest.json")

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            backup = args[i + 1]
            i += 2
        elif not target and not args[i].startswith("-"):
            target = args[i]
            i += 1
        else:
            i += 1

    if not target:
        target = settings.DATABASE_URL
        print(f"No target URL specified. Using DATABASE_URL from .env: {target[:25]}...")

    if not target:
        print("Error: Target database URL not provided and not found in settings!")
        sys.exit(1)

    asyncio.run(restore_database(target, backup))
