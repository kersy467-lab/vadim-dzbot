"""The NATBIRZHA 1.5 Pivocoin bonus is applied once per existing company."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
from backend.natbirzha.migrations import _migrate_v27_release_bonus_pivocoins
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.premium import NatPremiumLedgerEntry


def test_release_bonus_credits_each_company_once_and_records_ledger() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            users = [
                User(tg_id=701, full_name="Player One", role="student"),
                User(tg_id=702, full_name="Player Two", role="student"),
            ]
            session.add_all(users)
            await session.flush()
            companies = [
                NatCompany(user_id=users[0].id, name="One Corp", specialization="miner", pvc_balance=25),
                NatCompany(user_id=users[1].id, name="Two Corp", specialization="chemist", pvc_balance=0),
            ]
            session.add_all(companies)
            await session.commit()

        async with engine.begin() as connection:
            await _migrate_v27_release_bonus_pivocoins(connection)
        async with engine.begin() as connection:
            await _migrate_v27_release_bonus_pivocoins(connection)

        async with factory() as session:
            balances = list((await session.scalars(
                select(NatCompany.pvc_balance).order_by(NatCompany.id)
            )).all())
            entries = list((await session.scalars(
                select(NatPremiumLedgerEntry).order_by(NatPremiumLedgerEntry.company_id)
            )).all())
            assert balances == [2_025, 2_000]
            assert len(entries) == 2
            assert [entry.amount for entry in entries] == [2_000, 2_000]
            assert all(entry.operation_type == "release_bonus" for entry in entries)
            assert all(entry.metadata_json["release"] == "НАТБИРЖА 1.5" for entry in entries)

        await engine.dispose()

    asyncio.run(scenario())


if __name__ == "__main__":
    test_release_bonus_credits_each_company_once_and_records_ledger()
    print("NATBIRZHA 1.5 Pivocoin bonus migration checks: PASS")
