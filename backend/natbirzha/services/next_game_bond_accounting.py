"""Coupon accrual, secured reserve liabilities and forfeiture on rebirth."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from backend.natbirzha.models.next_game_bonds import (
    NatNextGameBondHolding, NatNextGameBondSeries, NatNextGameBondListing,
)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def money(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


async def required_liability(session):
    """Principal plus ALL unpaid coupon, including currently accrued interest."""
    rows = (await session.execute(select(NatNextGameBondHolding, NatNextGameBondSeries)
        .join(NatNextGameBondSeries, NatNextGameBondSeries.id == NatNextGameBondHolding.series_id)
        .where(NatNextGameBondHolding.status == "ACTIVE"))).all()
    return round(sum(holding.units * series.face_price + holding.coupon_remaining
                     for holding, series in rows), 8)


async def settle_holding(session, holding, series, company, treasury, *, now=None, force=False):
    # Callers serialize reserve and company changes before invoking this helper.
    from backend.natbirzha.services.next_game_service import NextGameService
    if holding.status != "ACTIVE":
        return 0.0
    current = now or utcnow()
    end = min(current, holding.matures_at)
    elapsed = max(0, (end - holding.last_coupon_at).total_seconds())
    seconds = elapsed if force or current >= holding.matures_at else int(elapsed // 3600) * 3600
    accrued_end = holding.last_coupon_at + timedelta(seconds=seconds)
    target = money(holding.units * series.face_price * series.daily_rate *
        max(0, (accrued_end - holding.accrual_started_at).total_seconds()) / 86400)
    coupon = min(holding.coupon_remaining, max(0, money(target - holding.accrual_paid)))
    if current >= holding.matures_at:
        # Splitting lots never grows the promised coupon; final cents settle here.
        coupon = holding.coupon_remaining
    if coupon > 0:
        treasury.cash = round(treasury.cash - coupon, 8)
        company.cash = round(company.cash + coupon, 8)
        holding.coupon_paid = money(holding.coupon_paid + coupon)
        holding.accrual_paid = money(holding.accrual_paid + coupon)
        holding.coupon_remaining = max(0, money(holding.coupon_remaining - coupon))
        session.add(NextGameService._ledger(company.id, "BOND_COUPON", coupon, -coupon,
            metadata={"holding_id": holding.id, "seconds": seconds}))
    if seconds > 0:
        holding.last_coupon_at = accrued_end
    if current >= holding.matures_at:
        principal = round(holding.units * series.face_price, 8)
        treasury.cash = round(treasury.cash - principal, 8)
        company.cash = round(company.cash + principal, 8)
        holding.status = "MATURED"
        listings = (await session.scalars(select(NatNextGameBondListing).where(
            NatNextGameBondListing.holding_id == holding.id, NatNextGameBondListing.status == "OPEN"))).all()
        for listing in listings:
            listing.status = "MATURED"
        session.add(NextGameService._ledger(company.id, "BOND_REDEEM", principal, -principal,
            metadata={"holding_id": holding.id}))
    await session.flush()
    return coupon


async def forfeit_company_holdings(session, company_id):
    """Rebirth destroys owned financial assets without settling pending coupons."""
    holdings = (await session.scalars(select(NatNextGameBondHolding).where(
        NatNextGameBondHolding.company_id == company_id, NatNextGameBondHolding.status == "ACTIVE",
    ).with_for_update())).all()
    for holding in holdings:
        holding.status = "FORFEITED"
    listings = (await session.scalars(select(NatNextGameBondListing).where(
        NatNextGameBondListing.seller_company_id == company_id,
        NatNextGameBondListing.status == "OPEN",
    ).with_for_update())).all()
    for listing in listings:
        listing.status = "FORFEITED"
    await session.flush()
    return {"forfeited_units": sum(row.units for row in holdings)}
