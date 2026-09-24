"""Admin state-bond bankruptcy compensation and idempotency checks."""

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import (
    NatBondListing,
    NatBondSettlement,
    NatCreatorAuditLog,
    NatStateBond,
    NatStateBondHolding,
    NatStateTreasury,
)
from backend.natbirzha.services.state_bond_service import StateBondService


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions


def test_bankruptcy_pays_thirty_percent_once_and_stops_future_settlements() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        issued_at = datetime(2026, 9, 1, 12)
        async with sessions() as session:
            first = NatCompany(user_id=921001, name="Holder One", specialization="miner", cash=20_000)
            second = NatCompany(user_id=921002, name="Holder Two", specialization="forester", cash=20_000)
            session.add_all([first, second])
            await session.flush()
            issue = await StateBondService.issue(
                session, actor_id=777, title="OFZ-DEFAULT", volume=10, face_value=1_000,
                coupon_rate=36.5, maturity_days=14, purpose="bankruptcy test", now=issued_at,
                commit=False,
            )
            await StateBondService.buy(session, first, issue["bond_id"], 4, now=issued_at, commit=False)
            await StateBondService.buy(session, second, issue["bond_id"], 3, now=issued_at, commit=False)
            await StateBondService.create_listing(
                session, first.id, issue["bond_id"], quantity=2, unit_price=900,
                operation_key="bankruptcy-listing", now=issued_at, commit=False,
            )
            treasury = await session.scalar(select(NatStateTreasury))
            treasury.cash = 20_000
            first_id, second_id, bond_id = first.id, second.id, issue["bond_id"]
            first_before, second_before = first.cash, second.cash
            await session.commit()

        async with sessions() as session:
            declared = await StateBondService.declare_bankruptcy(
                session, actor_id=777, bond_id=bond_id, now=issued_at, commit=True,
            )
            assert declared["status"] == "BANKRUPT"
            assert declared["holder_count"] == 2
            assert declared["units_compensated"] == 7
            assert declared["compensation_paid"] == 2_100
            assert declared["principal_written_off"] == 4_900

            first = await session.get(NatCompany, first_id)
            second = await session.get(NatCompany, second_id)
            treasury = await session.scalar(select(NatStateTreasury))
            assert first.cash == first_before + 1_200
            assert second.cash == second_before + 900
            assert treasury.cash == 17_900

            bond = await session.get(NatStateBond, bond_id)
            assert bond.is_active is False and bond.status == "BANKRUPT"
            assert bond.next_coupon_at is None
            holdings = (await session.execute(
                select(NatStateBondHolding).where(NatStateBondHolding.bond_id == bond_id)
            )).scalars().all()
            assert all(row.quantity == row.reserved_quantity == 0 for row in holdings)
            listing = await session.scalar(select(NatBondListing).where(NatBondListing.bond_id == bond_id))
            assert listing.status == "CANCELLED"
            with pytest.raises(ValueError, match="not available for secondary trading"):
                await StateBondService.create_listing(
                    session, first_id, bond_id, quantity=1, unit_price=900,
                    operation_key="bankruptcy-after-default", now=issued_at + timedelta(days=1),
                )
            audit = (await session.execute(select(NatCreatorAuditLog).where(
                NatCreatorAuditLog.action == "BOND_BANKRUPTCY",
                NatCreatorAuditLog.target_id == str(bond_id),
            ))).scalars().all()
            assert len(audit) == 1 and "4,900" in audit[0].details

            replay = await StateBondService.declare_bankruptcy(
                session, actor_id=777, bond_id=bond_id, now=issued_at + timedelta(days=1), commit=True,
            )
            assert replay["already_bankrupt"] is True
            assert replay["compensation_paid"] == 2_100
            assert treasury.cash == 17_900
            assert await session.scalar(select(func.count(NatBondSettlement.id))) == 2
            assert await session.scalar(select(func.count(NatCreatorAuditLog.id)).where(
                NatCreatorAuditLog.action == "BOND_BANKRUPTCY",
            )) == 1

            later = await StateBondService.settle_due(session, now=issued_at + timedelta(days=20))
            assert later["coupon_payments"] == later["maturity_payments"] == 0
            assert await session.scalar(select(func.count(NatBondSettlement.id))) == 2

        await engine.dispose()

    asyncio.run(check())


def test_bankruptcy_refuses_partial_compensation_when_treasury_is_short() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        issued_at = datetime(2026, 9, 1, 12)
        async with sessions() as session:
            holder = NatCompany(user_id=921003, name="Underfunded Holder", specialization="miner", cash=1_000)
            session.add(holder)
            await session.flush()
            issue = await StateBondService.issue(
                session, actor_id=777, title="OFZ-SHORT", volume=2, face_value=100,
                coupon_rate=0, maturity_days=30, purpose="insufficient treasury", now=issued_at,
                commit=False,
            )
            await StateBondService.buy(session, holder, issue["bond_id"], 1, now=issued_at, commit=False)
            treasury = await session.scalar(select(NatStateTreasury))
            treasury.cash = 29.99
            holder_id, bond_id = holder.id, issue["bond_id"]
            holder_before = holder.cash
            await session.commit()

        async with sessions() as session:
            with pytest.raises(ValueError, match="Insufficient Treasury"):
                await StateBondService.declare_bankruptcy(
                    session, actor_id=777, bond_id=bond_id, now=issued_at, commit=True,
                )
            await session.rollback()
            holder = await session.get(NatCompany, holder_id)
            treasury = await session.scalar(select(NatStateTreasury))
            bond = await session.get(NatStateBond, bond_id)
            assert holder.cash == holder_before
            assert treasury.cash == 29.99
            assert bond.status == "ACTIVE" and bond.is_active is True
            assert await session.scalar(select(func.count(NatBondSettlement.id))) == 0
            assert await session.scalar(select(func.count(NatCreatorAuditLog.id)).where(
                NatCreatorAuditLog.action == "BOND_BANKRUPTCY",
            )) == 0

        await engine.dispose()

    asyncio.run(check())


def test_bankruptcy_cancels_already_pending_maturity_principal() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        issued_at = datetime(2026, 9, 1, 12)
        maturity_at = issued_at + timedelta(days=1)
        async with sessions() as session:
            holder = NatCompany(user_id=921004, name="Maturity Holder", specialization="miner", cash=1_000)
            session.add(holder)
            await session.flush()
            issue = await StateBondService.issue(
                session, actor_id=777, title="OFZ-MATURITY", volume=2, face_value=100,
                coupon_rate=0, maturity_days=1, purpose="maturity cancellation", now=issued_at,
                commit=False,
            )
            await StateBondService.buy(session, holder, issue["bond_id"], 1, now=issued_at, commit=False)
            treasury = await session.scalar(select(NatStateTreasury))
            treasury.cash = 0
            holder_id, bond_id = holder.id, issue["bond_id"]
            before = holder.cash
            await session.commit()

        async with sessions() as session:
            unpaid = await StateBondService.settle_due(session, now=maturity_at, commit=True)
            assert unpaid["maturity_pending"] == 1

            treasury = await session.scalar(select(NatStateTreasury))
            treasury.cash = 30
            await session.commit()
            result = await StateBondService.declare_bankruptcy(
                session, actor_id=777, bond_id=bond_id, now=maturity_at, commit=True,
            )
            assert result["compensation_paid"] == 30
            principal = await session.scalar(select(NatBondSettlement).where(
                NatBondSettlement.bond_id == bond_id,
                NatBondSettlement.settlement_type == "PRINCIPAL",
            ))
            assert principal.status == "CANCELLED"

            later = await StateBondService.settle_due(
                session, now=maturity_at + timedelta(days=1), commit=True,
            )
            holder = await session.get(NatCompany, holder_id)
            treasury = await session.scalar(select(NatStateTreasury))
            assert later["maturity_payments"] == later["principal_paid_rub"] == 0
            assert holder.cash == before + 30
            assert treasury.cash == 0

        await engine.dispose()

    asyncio.run(check())


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", __file__]))
