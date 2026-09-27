import os
import asyncio
from unittest.mock import patch

from sqlalchemy.pool import NullPool

from backend.db import session as db_session


def _capture_engine_options(database_url: str) -> dict:
    with patch.dict(os.environ, {"DATABASE_URL": database_url}), patch.object(
        db_session, "create_async_engine", return_value=object()
    ) as create_engine:
        db_session.create_configured_engine()
    return create_engine.call_args.kwargs


def test_supabase_transaction_pooler_uses_transaction_safe_engine_options():
    options = _capture_engine_options(
        "postgresql://postgres.project:secret@aws-0-eu-west-1.pooler.supabase.com:6543/"
        "postgres?sslmode=require&channel_binding=require"
    )

    assert options["poolclass"] is NullPool
    assert options["connect_args"]["ssl"] == "require"
    assert options["connect_args"]["statement_cache_size"] == 0
    assert options["url"].query["prepared_statement_cache_size"] == "0"
    assert "pool_size" not in options
    assert "max_overflow" not in options


def test_supabase_session_pooler_uses_a_bounded_connection_pool():
    options = _capture_engine_options(
        "postgresql://postgres.project:secret@aws-0-eu-west-1.pooler.supabase.com:5432/"
        "postgres?sslmode=require"
    )

    assert options["connect_args"]["ssl"] == "require"
    assert options["pool_size"] == 5
    assert options["max_overflow"] == 5
    assert "poolclass" not in options or options["poolclass"] is not NullPool


def test_real_engine_builds_for_supabase_session_and_transaction_poolers():
    urls = (
        "postgresql://postgres.project:secret@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require",
        "postgresql://postgres.project:secret@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require",
    )
    engines = []
    try:
        for database_url in urls:
            with patch.dict(os.environ, {"DATABASE_URL": database_url}):
                engine = db_session.create_configured_engine()
            engines.append(engine)

        assert engines[0].sync_engine.pool.size() == 5
        assert isinstance(engines[1].sync_engine.pool, NullPool)
        assert engines[1].sync_engine.url.query["prepared_statement_cache_size"] == "0"
    finally:
        for engine in engines:
            asyncio.run(engine.dispose())


if __name__ == "__main__":
    test_supabase_transaction_pooler_uses_transaction_safe_engine_options()
    test_supabase_session_pooler_uses_a_bounded_connection_pool()
    test_real_engine_builds_for_supabase_session_and_transaction_poolers()
    print("Database connection configuration checks: PASS")
