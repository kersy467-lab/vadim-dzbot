"""State-bond coupons accrue every minute from the configured daily yield."""

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateBond
from backend.natbirzha.services.state_bond_service import StateBondService


def test_coupon_rate_of_30_percent_yields_15_percent_per_day() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        issued_at = datetime(2026, 9, 24, 12)
        async with sessions() as session:
            buyer = NatCompany(user_id=952001, name="Minute Bond Buyer", specialization="miner", cash=20_000)
            session.add(buyer)
            await session.flush()
            issue = await StateBondService.issue(
                session,
                actor_id=777,
                title="ОФЗ-Минута",
                volume=10,
                face_value=1_000,
                coupon_rate=30,
                maturity_days=30,
                purpose="minute coupon",
                now=issued_at,
                commit=False,
            )
            assert issue["next_coupon_at"] == (issued_at + timedelta(minutes=1)).isoformat()
            bond = await session.scalar(select(NatStateBond).where(NatStateBond.id == issue["bond_id"]))
            await StateBondService.buy(session, buyer, bond.id, 1, now=issued_at, commit=False)
            await session.commit()

        async with sessions() as session:
            first_tick = await StateBondService.settle_due(
                session, now=issued_at + timedelta(minutes=1)
            )
            one_minute = 1_000 * 0.15 / 1_440
            assert first_tick["coupon_payments"] == 1
            assert first_tick["coupon_paid_rub"] == round(one_minute, 2)

            replay = await StateBondService.settle_due(
                session, now=issued_at + timedelta(minutes=1)
            )
            assert replay["coupon_payments"] == 0

            late_buyer = NatCompany(
                user_id=952002, name="Late Bond Buyer", specialization="miner", cash=20_000
            )
            session.add(late_buyer)
            await session.flush()
            await StateBondService.buy(
                session, late_buyer, bond.id, 1,
                now=issued_at + timedelta(minutes=2), commit=False,
            )
            # The elapsed minute is paid to the original holder before the new
            # buyer acquires the bond, so there is no backdated coupon.
            assert late_buyer.cash == 19_000

            catch_up = await StateBondService.settle_due(
                session, now=issued_at + timedelta(minutes=3)
            )
            assert catch_up["coupon_payments"] == 2
            assert catch_up["coupon_paid_rub"] == round(one_minute * 2, 2)

        await engine.dispose()

    asyncio.run(run())


def test_bond_scheduler_runs_each_minute() -> None:
    source = Path("backend/bot/services/scheduler.py").read_text(encoding="utf-8")
    job = re.search(
        r"scheduler\.add_job\(\s*run_natbirzha_bond_settlement,\s*"
        r"trigger=CronTrigger\((.*?)\),\s*id=\"natbirzha_bond_settlement_job\"",
        source,
        re.DOTALL,
    )
    assert job and 'minute="*"' in job.group(1)
