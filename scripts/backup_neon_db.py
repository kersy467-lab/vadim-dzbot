"""Database backup utility for Neon / PostgreSQL.
Exports all tables and data into JSON and SQL formats with topological dependency order.
"""

import asyncio
import os
import sys
import json
from datetime import datetime, date
from decimal import Decimal
import uuid

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from backend.db.session import async_session_factory
from backend.db.models import Base
import backend.natbirzha.models  # Ensure all models are registered


def json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Type {type(obj)} not serializable")


def sql_quote(val):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, (datetime, date)):
        return f"'{val.isoformat()}'"
    if isinstance(val, (dict, list)):
        escaped = json.dumps(val, ensure_ascii=False, default=json_serializer).replace("'", "''")
        return f"'{escaped}'"
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


async def run_backup():
    os.makedirs(os.path.join("data", "backups"), exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join("data", "backups", f"neon_backup_{timestamp}.json")
    latest_json_path = os.path.join("data", "backups", "neon_backup_latest.json")
    sql_path = os.path.join("data", "backups", f"neon_backup_{timestamp}.sql")
    latest_sql_path = os.path.join("data", "backups", "neon_backup_latest.sql")

    print(f"Connecting to database to dump backup...")
    backup_data = {
        "metadata": {
            "created_at": datetime.utcnow().isoformat(),
            "timestamp": timestamp,
            "version": "1.0",
        },
        "tables": {},
    }

    sql_statements = [
        "-- NEON POSTGRESQL DATABASE BACKUP",
        f"-- Created at: {datetime.utcnow().isoformat()}",
        "SET session_replication_role = 'replica'; -- Disable triggers and foreign keys during restore",
        "BEGIN;\n",
    ]

    async with async_session_factory() as session:
        # Get all existing tables in public schema
        res = await session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        existing_tables = set(r[0] for r in res.fetchall())
        print(f"Found {len(existing_tables)} tables in database.")

        # Ordered tables: use Base.metadata.sorted_tables for dependency ordering, then any extras
        ordered_table_names = []
        for t in Base.metadata.sorted_tables:
            if t.name in existing_tables:
                ordered_table_names.append(t.name)
        for t in sorted(existing_tables):
            if t not in ordered_table_names:
                ordered_table_names.append(t)

        total_rows = 0
        summary_rows = []

        for tbl in ordered_table_names:
            try:
                # Query all columns and rows
                col_res = await session.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = :t
                    ORDER BY ordinal_position
                """), {"t": tbl})
                columns = [r[0] for r in col_res.fetchall()]

                rows_res = await session.execute(text(f'SELECT * FROM "{tbl}"'))
                raw_rows = rows_res.fetchall()

                rows_list = []
                for row in raw_rows:
                    row_dict = {}
                    for col, val in zip(columns, row):
                        row_dict[col] = val
                    rows_list.append(row_dict)

                row_count = len(rows_list)
                total_rows += row_count
                if row_count > 0:
                    summary_rows.append((tbl, row_count))

                backup_data["tables"][tbl] = {
                    "columns": columns,
                    "rows": rows_list,
                    "count": row_count,
                }

                # Generate SQL INSERTs
                if row_count > 0:
                    sql_statements.append(f"-- Table: {tbl} ({row_count} rows)")
                    col_names = ", ".join(f'"{c}"' for c in columns)
                    for r in raw_rows:
                        vals = ", ".join(sql_quote(v) for v in r)
                        sql_statements.append(f'INSERT INTO "{tbl}" ({col_names}) VALUES ({vals});')
                    sql_statements.append("")

            except Exception as exc:
                print(f"  Warning: failed to dump table {tbl}: {exc}")

        # Fix sequence values for autoincrement primary keys
        sql_statements.append("-- Reset sequences to max values")
        seq_res = await session.execute(text("""
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
        """))
        for seq_row in seq_res.fetchall():
            seq_name = seq_row[0]
            # Try matching sequence to table_id
            parts = seq_name.split("_")
            if len(parts) >= 2:
                tbl_guess = "_".join(parts[:-2]) if parts[-1] == "seq" else parts[0]
                col_guess = parts[-2] if parts[-1] == "seq" else "id"
                if tbl_guess in existing_tables:
                    sql_statements.append(
                        f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(\"{col_guess}\") FROM \"{tbl_guess}\"), 1), true);"
                    )

        sql_statements.append("\nCOMMIT;")
        sql_statements.append("SET session_replication_role = 'origin'; -- Re-enable triggers and foreign keys")

    # Write JSON backup
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2, default=json_serializer)
    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2, default=json_serializer)

    # Write SQL backup
    sql_text = "\n".join(sql_statements)
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(sql_text)
    with open(latest_sql_path, "w", encoding="utf-8") as f:
        f.write(sql_text)

    json_size_mb = os.path.getsize(json_path) / (1024 * 1024)
    sql_size_mb = os.path.getsize(sql_path) / (1024 * 1024)

    print("\n" + "=" * 60)
    print("BACKUP COMPLETED SUCCESSFULLY!")
    print(f"Total tables with data: {len(summary_rows)}")
    print(f"Total rows backed up: {total_rows}")
    print(f"JSON backup file: {json_path} ({json_size_mb:.2f} MB)")
    print(f"SQL backup file:  {sql_path} ({sql_size_mb:.2f} MB)")
    print("=" * 60)
    print("\nNon-empty tables summary:")
    for t, cnt in sorted(summary_rows, key=lambda x: x[1], reverse=True):
        print(f"  - {t}: {cnt} rows")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_backup())
