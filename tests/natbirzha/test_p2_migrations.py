"""Repeatable migration from the legacy NATBIRZHA army and NAT balance."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.natbirzha.migrations import MIGRATIONS, run_natbirzha_migrations


async def run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE nat_companies (
                id INTEGER PRIMARY KEY,
                nat_balance INTEGER NOT NULL DEFAULT 0
            )
        """))
        await conn.execute(text("""
            CREATE TABLE nat_armies (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL UNIQUE,
                infantry INTEGER NOT NULL DEFAULT 0,
                tanks INTEGER NOT NULL DEFAULT 0,
                drones INTEGER NOT NULL DEFAULT 0,
                air_defense INTEGER NOT NULL DEFAULT 0
            )
        """))
        await conn.execute(text("""
            CREATE TABLE nat_army_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                unit_type VARCHAR(32) NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                readiness INTEGER NOT NULL DEFAULT 10000,
                experience BIGINT NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, unit_type)
            )
        """))
        await conn.execute(text("""
            CREATE TABLE nat_state_bonds (
                id INTEGER PRIMARY KEY,
                title VARCHAR(100) NOT NULL,
                total_volume INTEGER NOT NULL,
                remaining_volume INTEGER NOT NULL,
                face_value FLOAT NOT NULL,
                coupon_rate FLOAT NOT NULL,
                maturity_days INTEGER NOT NULL,
                purpose VARCHAR(255) NOT NULL,
                actor_id BIGINT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL
            )
        """))
        await conn.execute(text("""
            CREATE TABLE nat_state_bond_holdings (
                id INTEGER PRIMARY KEY,
                bond_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                invested_cash FLOAT NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL
            )
        """))
        await conn.execute(text("INSERT INTO nat_companies (id, nat_balance) VALUES (1, 37)"))
        await conn.execute(text("""
            INSERT INTO nat_armies (company_id, infantry, tanks, drones, air_defense)
            VALUES (1, 12, 2, 3, 1)
        """))
        await conn.execute(text("""
            INSERT INTO nat_state_bonds
                (id, title, total_volume, remaining_volume, face_value, coupon_rate,
                 maturity_days, purpose, actor_id, is_active, created_at)
            VALUES (1, 'Legacy OFZ', 10, 4, 1000, 10, 30, 'migration', 777, 1, '2026-09-01 12:00:00')
        """))
        await conn.execute(text("""
            INSERT INTO nat_state_bond_holdings
                (id, bond_id, company_id, quantity, invested_cash, updated_at)
            VALUES (1, 1, 1, 6, 6000, '2026-09-01 12:00:00')
        """))

        await run_natbirzha_migrations(conn)
        await run_natbirzha_migrations(conn)

        row = (await conn.execute(text(
            "SELECT pvc_balance, military_rating FROM nat_companies WHERE id = 1"
        ))).one()
        assert row.pvc_balance == 37
        assert row.military_rating == 1000

        units = dict((await conn.execute(text(
            "SELECT unit_type, quantity FROM nat_army_units ORDER BY unit_type"
        ))).all())
        assert units == {
            "air_defense": 1,
            "drones": 3,
            "infantry": 12,
            "tanks": 2,
        }
        bond = (await conn.execute(text("""
            SELECT coupon_interval_days, status, next_coupon_at, maturity_at
            FROM nat_state_bonds WHERE id = 1
        """))).one()
        assert bond.coupon_interval_days == 1
        assert bond.status == "ACTIVE"
        assert str(bond.next_coupon_at).startswith("2026-09-02")
        assert str(bond.maturity_at).startswith("2026-10-01")
        reserved = (await conn.execute(text(
            "SELECT reserved_quantity FROM nat_state_bond_holdings WHERE id = 1"
        ))).scalar_one()
        assert reserved == 0
        versions = (await conn.execute(text(
            "SELECT version, COUNT(*) FROM nat_schema_versions GROUP BY version ORDER BY version"
        ))).all()
        assert versions == sorted([(version, 1) for version, _ in MIGRATIONS])

    await engine.dispose()
    print("NATBIRZHA P2 migration checks: PASS")


if __name__ == "__main__":
    asyncio.run(run())
