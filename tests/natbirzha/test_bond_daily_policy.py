"""Daily coupon policy for newly issued state bonds."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateBond
from backend.natbirzha.services.state_bond_service import StateBondService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    issued_at = datetime(2026, 9, 1, 12, 0)
    async with sessions() as session:
        buyer = NatCompany(user_id=940001, name="Daily Bond Buyer", specialization="miner", cash=20_000)
        session.add(buyer)
        await session.flush()
        issue = await StateBondService.issue(
            session, actor_id=777, title="ОФЗ-День", volume=10, face_value=1_000,
            coupon_rate=25, maturity_days=30, purpose="daily coupon", now=issued_at, commit=False,
        )
        assert issue["next_coupon_at"].startswith("2026-09-02"), "new bonds must schedule the first coupon after 24 hours"
        bond = await session.scalar(select(NatStateBond).where(NatStateBond.id == issue["bond_id"]))
        assert bond.coupon_interval_days == 1
        await StateBondService.buy(session, buyer, bond.id, 1, now=issued_at, commit=False)
        await session.commit()

    async with sessions() as session:
        result = await StateBondService.settle_due(session, now=issued_at + timedelta(days=1))
        # 25% annual rate is prorated over 365 daily settlements.
        assert result["coupon_payments"] == 1
        assert result["coupon_paid_rub"] == round(1000 * 0.25 / 365, 2)

    await engine.dispose()
    print("NATBIRZHA daily bond policy checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
