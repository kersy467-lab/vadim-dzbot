"""State-bond coupon, maturity and secondary-market accounting checks."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondSettlement, NatStateBondHolding, NatStateTreasury
from backend.natbirzha.services.state_bond_service import StateBondService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    issued_at = datetime(2026, 9, 1, 12, 0)
    async with sessions() as session:
        seller = NatCompany(user_id=930001, name="Bond Seller", specialization="miner", cash=20_000)
        buyer = NatCompany(user_id=930002, name="Bond Buyer 2", specialization="forester", cash=20_000)
        session.add_all([seller, buyer])
        await session.flush()
        issue = await StateBondService.issue(
            session,
            actor_id=777,
            title="ОФЗ-P2",
            volume=10,
            face_value=1_000,
            coupon_rate=36.5,
            maturity_days=14,
            purpose="P2 test",
            coupon_interval_days=7,
            now=issued_at,
            commit=False,
        )
        await StateBondService.buy(session, seller, issue["bond_id"], 10, now=issued_at, commit=False)
        await session.commit()
        seller_id, buyer_id, bond_id = seller.id, buyer.id, issue["bond_id"]

    async with sessions() as session:
        seller = await session.get(NatCompany, seller_id)
        treasury = await session.scalar(select(NatStateTreasury))
        seller_cash = seller.cash
        treasury_cash = treasury.cash
        first = await StateBondService.settle_due(session, now=issued_at + timedelta(days=7))
        assert first["coupon_payments"] == 1 and first["coupon_paid_rub"] == 70.0
        await session.commit()
        assert seller.cash == seller_cash + 70
        assert treasury.cash == treasury_cash - 70

        # Exact replay at the same moment cannot pay the same coupon twice.
        replay = await StateBondService.settle_due(session, now=issued_at + timedelta(days=7))
        assert replay["coupon_payments"] == 0 and replay["coupon_paid_rub"] == 0

        listing = await StateBondService.create_listing(
            session, seller_id, bond_id, quantity=4, unit_price=1_100, operation_key="listing:1",
            now=issued_at + timedelta(days=8),
        )
        bought = await StateBondService.buy_listing(
            session, buyer_id, listing["listing_id"], operation_key="listing-buy:1",
            now=issued_at + timedelta(days=8),
        )
        assert bought["total_cost"] == 4_400
        replay_buy = await StateBondService.buy_listing(
            session, buyer_id, listing["listing_id"], operation_key="listing-buy:1",
            now=issued_at + timedelta(days=8),
        )
        assert replay_buy == bought
        await session.commit()

        seller_holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == bond_id, NatStateBondHolding.company_id == seller_id
        ))
        buyer_holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == bond_id, NatStateBondHolding.company_id == buyer_id
        ))
        assert seller_holding.quantity == 6 and seller_holding.reserved_quantity == 0
        assert buyer_holding.quantity == 4

        # Empty treasury creates pending maturity settlements and never mints money.
        treasury.cash = 0
        seller_before = seller.cash
        buyer = await session.get(NatCompany, buyer_id)
        buyer_before = buyer.cash
        pending = await StateBondService.settle_due(session, now=issued_at + timedelta(days=14))
        assert pending["maturity_pending"] == 2 and pending["principal_paid_rub"] == 0
        assert seller.cash == seller_before and buyer.cash == buyer_before
        await session.commit()

        treasury.cash = 20_000
        settled = await StateBondService.settle_due(session, now=issued_at + timedelta(days=14))
        assert settled["coupon_payments"] == 2
        assert settled["coupon_paid_rub"] == 70
        assert settled["maturity_payments"] == 2
        assert settled["principal_paid_rub"] == 10_000
        await session.commit()
        assert seller.cash == seller_before + 6_042
        assert buyer.cash == buyer_before + 4_028

        settlement_count = await session.scalar(select(func.count(NatBondSettlement.id)))
        assert settlement_count == 5  # first coupon, then two final coupons and two principal payments

    await engine.dispose()
    print("NATBIRZHA bond lifecycle checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
