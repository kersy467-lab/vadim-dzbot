"""Creator rebirth scheduling closes joint plants without stranding partners."""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.joint_factories import NatJointFactory
from backend.natbirzha.services.admin_rebirth_schedule_service import (
    _close_joint_factories,
    _warning_message,
)


async def run_async():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime(2026, 10, 9, 12, 0)
    async with sessions() as session:
        users = [
            User(tg_id=987001, full_name="Target A", role="admin"),
            User(tg_id=987002, full_name="Target B", role="admin"),
            User(tg_id=987003, full_name="Partner C", role="public"),
        ]
        session.add_all(users)
        await session.flush()
        companies = [
            NatCompany(user_id=users[0].id, name="Target A Co", specialization="ai_data"),
            NatCompany(user_id=users[1].id, name="Target B Co", specialization="chemist"),
            NatCompany(user_id=users[2].id, name="Partner C Co", specialization="chemist"),
        ]
        session.add_all(companies)
        await session.flush()
        factory = NatJointFactory(
            recipe_id="joint_ai_data_chemist",
            company_a_id=companies[0].id,
            company_b_id=companies[2].id,
            level=1,
            status="ACTIVE",
            stock_a_json={"ai_compute": 4.0},
            stock_b_json={"fertilizer": 7.5},
            last_settled_at=now,
            created_at=now,
        )
        session.add(factory)
        await session.commit()

        await _close_joint_factories(session, {companies[0].id, companies[1].id}, now)
        closed = await session.get(NatJointFactory, factory.id)
        partner_stock = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == companies[2].id,
            NatInventory.item_id == "fertilizer",
        ))
        target_stock = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == companies[0].id,
            NatInventory.item_id == "ai_compute",
        ))
        assert closed.status == "BREACHED"
        assert closed.stock_a_json == {} and closed.stock_b_json == {}
        assert partner_stock is not None and partner_stock.quantity == 7.5
        assert target_stock is None

    await engine.dispose()


def run():
    asyncio.run(run_async())
    warning = _warning_message(
        [NatCompany(name="A & B", custom_ticker="AB", specialization="ai_data")],
        datetime(2026, 10, 9, 12, 10),
    )
    assert "A &amp; B" in warning
    assert "99%" in warning and "дивиденды" in warning and "12:10:00" in warning
    print("Admin rebirth delayed warning and joint-factory settlement: PASS")


if __name__ == "__main__":
    run()
