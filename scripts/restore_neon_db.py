"""Restore database from SQL or JSON backup into any PostgreSQL database.
Usage:
    python scripts/restore_neon_db.py [NEW_DATABASE_URL] [--file path_to_backup.sql|.json]
"""

import asyncio
import os
import sys
import json
import urllib.parse
from datetime import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from backend.db.models import Base
import backend.natbirzha.models  # Register all models


def parse_pg_url(url: str):
    """Parse PostgreSQL URL into connection parameters."""
    clean = url
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break

    user_pass, host_db = clean.split("@", 1)
    if ":" in user_pass:
        user, password = user_pass.split(":", 1)
    else:
        user, password = user_pass, ""

    user = urllib.parse.unquote(user)
    password = urllib.parse.unquote(password)

    if "?" in host_db:
        host_db, _ = host_db.split("?", 1)

    host_port, database = host_db.split("/", 1)
    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        port = int(port_str)
    else:
        host, port = host_port, 5432

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


async def restore_from_sql(target_url: str, sql_file: str):
    print(f"Loading SQL backup statements from {sql_file}...")
    with open(sql_file, "r", encoding="utf-8") as f:
        statements = [line.strip() for line in f if line.strip() and not line.strip().startswith("--")]

    total_stmts = len(statements)
    print(f"Total SQL statements to execute: {total_stmts}")

    params = parse_pg_url(target_url)
    ssl_mode = "require" if any(k in target_url.lower() for k in ("neon.tech", "supabase")) else None

    # 1. Ensure all schema tables exist via SQLAlchemy metadata first
    clean_url = target_url
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif clean_url.startswith("postgresql://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "?" in clean_url:
        clean_url = clean_url.split("?", 1)[0]

    connect_args = {}
    if ssl_mode:
        connect_args["ssl"] = ssl_mode
    if ":6543" in clean_url or "pooler.supabase" in clean_url:
        connect_args["statement_cache_size"] = 0

    print("Verifying / creating schema tables in target database...")
    engine = create_async_engine(clean_url, echo=False, connect_args=connect_args)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS nat_schema_versions (
                version VARCHAR(80) PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """))
    await engine.dispose()

    # 2. Connect via asyncpg to batch-execute the SQL dump
    print(f"Connecting to target database ({params['host']}:{params['port']})...")
    conn = await asyncpg.connect(
        host=params["host"],
        port=params["port"],
        user=params["user"],
        password=params["password"],
        database=params["database"],
        ssl=ssl_mode,
        statement_cache_size=0 if ("6543" in str(params["port"]) or "pooler.supabase" in params["host"]) else 100,
    )

    try:
        print("Executing backup statements in batches of 500...")
        chunk_size = 500
        for i in range(0, total_stmts, chunk_size):
            chunk = statements[i:i + chunk_size]
            batch_sql = "\n".join(chunk)
            await conn.execute(batch_sql)
            progress = min(i + chunk_size, total_stmts)
            pct = (progress / total_stmts) * 100
            print(f"Progress: {progress}/{total_stmts} ({pct:.1f}%) statements executed...")
    finally:
        await conn.close()

    print("\n" + "=" * 60)
    print("RESTORE COMPLETED SUCCESSFULLY!")
    print(f"Total statements executed: {total_stmts}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    from backend.config import settings
    target = None
    default_sql = os.path.join("data", "backups", "neon_backup_latest.sql")
    backup = default_sql

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

    asyncio.run(restore_from_sql(target, backup))
