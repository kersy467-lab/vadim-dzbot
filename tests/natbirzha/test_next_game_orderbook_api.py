import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_mock_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api.next_game_routes import router as next_game_router
from backend.natbirzha.config import nat_settings
from backend.natbirzha.next_game_market_migration import migrate_next_game_market
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user


def test_market_routes_are_admin_only_and_order_mutations_are_idempotent():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        previous_ids = nat_settings.CREATOR_TG_IDS
        actor = {"user": User(id=1, tg_id=81801, username="market", full_name="Market", role="student")}

        async def db_session():
            async with sessions() as session:
                yield session

        async def current_user():
            return actor["user"]

        app = FastAPI()
        app.include_router(next_game_router, prefix="/api/natbirzha")
        app.dependency_overrides[get_db_session] = db_session
        app.dependency_overrides[get_strict_natbirzha_user] = current_user
        nat_settings.CREATOR_TG_IDS = "81801"
        try:
            with TestClient(app) as client:
                actor["user"] = User(id=2, tg_id=81802, username="guest", full_name="Guest", role="student")
                assert client.get("/api/natbirzha/next-game/market/orders").status_code == 403
                denied = client.post(
                    "/api/natbirzha/next-game/market/orders",
                    json={"item_id": "energy", "side": "BUY", "quantity": 1, "limit_price": 2},
                    headers={"Idempotency-Key": "denied-order"},
                )
                assert denied.status_code == 403
                actor["user"] = User(id=1, tg_id=81801, username="market", full_name="Market", role="student")
                client.post("/api/natbirzha/next-game/company", json={"name": "Рынок API"})
                body = {"item_id": "energy", "side": "BUY", "quantity": 1, "limit_price": 2}
                headers = {"Idempotency-Key": "market-order-1"}
                first = client.post("/api/natbirzha/next-game/market/orders", json=body, headers=headers)
                replay = client.post("/api/natbirzha/next-game/market/orders", json=body, headers=headers)
                assert first.status_code == replay.status_code == 200
                assert first.json() == replay.json()
                assert len(first.json()["trades"]) == 0
                too_precise = client.post(
                    "/api/natbirzha/next-game/market/orders",
                    json={**body, "limit_price": 2.00001},
                    headers={"Idempotency-Key": "market-order-price-precision"},
                )
                assert too_precise.status_code == 422
                assert len(client.get("/api/natbirzha/next-game/market/orders?item_id=energy").json()["open_orders"]) == 1
                assert len(client.get("/api/natbirzha/next-game/market/orders/mine").json()["orders"]) == 1
                order_id = first.json()["order"]["id"]
                cancel_headers = {"Idempotency-Key": "market-cancel-1"}
                cancelled = client.delete(
                    f"/api/natbirzha/next-game/market/orders/{order_id}", headers=cancel_headers,
                )
                replay_cancel = client.delete(
                    f"/api/natbirzha/next-game/market/orders/{order_id}", headers=cancel_headers,
                )
                assert cancelled.status_code == replay_cancel.status_code == 200
                assert cancelled.json() == replay_cancel.json()
                assert cancelled.json()["order"]["status"] == "CANCELLED"
        finally:
            nat_settings.CREATOR_TG_IDS = previous_ids
            await engine.dispose()

    asyncio.run(check())


def test_market_migration_is_repeatable_and_creates_separate_tables():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("""
                CREATE TABLE nat_next_game_companies (
                    id INTEGER PRIMARY KEY, owner_tg_id BIGINT NOT NULL UNIQUE,
                    name VARCHAR(80) NOT NULL, sector_id VARCHAR(48),
                    branch_path JSON NOT NULL DEFAULT '[]', level INTEGER NOT NULL DEFAULT 1,
                    xp INTEGER NOT NULL DEFAULT 0, cash FLOAT NOT NULL,
                    created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
                )
            """))
            await migrate_next_game_market(connection)
            await migrate_next_game_market(connection)
            rows = await connection.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'nat_next_game_market_%'"
            ))
            assert {row[0] for row in rows.fetchall()} >= {
                "nat_next_game_market_orders", "nat_next_game_market_trades",
            }
        await engine.dispose()

    asyncio.run(check())


def test_market_migration_postgresql_path_checks_tables_before_creating_them():
    created_tables = {"nat_next_game_companies"}
    create_statements = []

    def capture(statement, *args, **kwargs):
        sql = str(statement.compile(dialect=engine.dialect)).lstrip()
        if sql.startswith("CREATE TABLE "):
            table_name = sql.split()[2]
            create_statements.append(table_name)
            created_tables.add(table_name)

    engine = create_mock_engine("postgresql://", capture)

    class Result:
        def __init__(self, row):
            self.row = row

        def first(self):
            return self.row

    class AsyncConnection:
        dialect = SimpleNamespace(name="postgresql")

        async def execute(self, statement, params=None):
            assert "information_schema.tables" in str(statement)
            return Result((1,) if params["table_name"] in created_tables else None)

        async def run_sync(self, operation):
            return operation(engine)

    async def check():
        connection = AsyncConnection()
        await migrate_next_game_market(connection)
        await migrate_next_game_market(connection)
        assert sorted(create_statements) == [
            "nat_next_game_market_orders", "nat_next_game_market_trades",
        ]

    asyncio.run(check())


def test_market_screen_exposes_bid_ask_book_limit_forms_and_cancel_controls():
    screen = "\n".join(Path(f"frontend/natbirzha/js/screens/{name}.js").read_text(encoding="utf-8") for name in ("next_game_market", "next_game_market_item"))
    api = Path("frontend/natbirzha/js/next_game_api.js").read_text(encoding="utf-8")
    assert "Bids" in screen and "Asks" in screen
    assert "createNextGameLimitOrder" in screen
    assert "cancelNextGameOrder" in screen
    assert 'Number(data.reference_price || item.base_price)' in screen
    assert 'step="0.0001"' in screen
    assert "createNextGameLimitOrder:" in api
    assert "cancelNextGameOrder:" in api
    assert "history" in screen or "recent_trades" in screen
