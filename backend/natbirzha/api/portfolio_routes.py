from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.config import get_game_now, get_game_today
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondSettlement, NatStateBond, NatStateBondHolding
from backend.natbirzha.models.instruments import NatInstrumentPosition, NatReferenceRateSnapshot
from backend.natbirzha.models.stocks import NatDividend, NatDividendPayment, NatStock, NatStockHolding
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.reference_instrument_service import ReferenceInstrumentService


router = APIRouter(prefix="/portfolio", tags=["Natbirzha Portfolio"])


@router.get("")
async def get_unified_portfolio(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    """Return one market portfolio view for every investment instrument."""
    stock_rows = (await session.execute(
        select(NatStockHolding, NatStock, NatCompany)
        .join(NatStock, NatStockHolding.stock_id == NatStock.id)
        .join(NatCompany, NatStock.company_id == NatCompany.id)
        .where(
            NatStockHolding.holder_company_id == company.id,
            NatStockHolding.shares_count > 0,
        )
        .order_by(NatStockHolding.id.desc())
    )).all()

    stock_ids = [stock.id for _, stock, _ in stock_rows]
    payment_totals: dict[int, float] = {}
    payment_rows = (await session.execute(
        select(NatDividendPayment, NatStock, NatCompany)
        .join(NatStock, NatDividendPayment.stock_id == NatStock.id)
        .join(NatCompany, NatStock.company_id == NatCompany.id)
        .where(NatDividendPayment.holder_company_id == company.id)
        .order_by(NatDividendPayment.settlement_date.desc(), NatDividendPayment.id.desc())
    )).all()
    for payment, _, _ in payment_rows:
        payment_totals[payment.stock_id] = round(
            payment_totals.get(payment.stock_id, 0.0) + payment.payout_cash, 2
        )
    latest_dividends: dict[int, NatDividend] = {}
    if stock_ids:
        dividend_rows = (await session.execute(
            select(NatDividend)
            .where(NatDividend.stock_id.in_(stock_ids))
            .order_by(NatDividend.settlement_date.desc(), NatDividend.id.desc())
        )).scalars().all()
        for dividend in dividend_rows:
            latest_dividends.setdefault(dividend.stock_id, dividend)

    next_dividend_at = datetime.combine(
        get_game_today() + timedelta(days=1), time(0, 1)
    ).isoformat()
    stocks = []
    for holding, stock, issuer in stock_rows:
        invested = round(holding.shares_count * holding.avg_price, 2)
        market_value = round(holding.shares_count * stock.current_price, 2)
        latest = latest_dividends.get(stock.id)
        stocks.append({
            "stock_id": stock.id,
            "issuer_company": issuer.name,
            "shares_count": holding.shares_count,
            "avg_buy_price": holding.avg_price,
            "current_market_price": stock.current_price,
            "invested_value": invested,
            "market_value": market_value,
            "unrealized_pnl": round(market_value - invested, 2),
            "dividends_earned": payment_totals.get(stock.id, 0.0),
            "latest_dividend_per_share": latest.per_share_amount if latest else 0.0,
            "latest_dividend_date": str(latest.settlement_date) if latest else None,
            "next_dividend_at": next_dividend_at if stock.is_listed else None,
        })

    bond_rows = (await session.execute(
        select(NatStateBondHolding, NatStateBond)
        .join(NatStateBond, NatStateBondHolding.bond_id == NatStateBond.id)
        .where(NatStateBondHolding.company_id == company.id, NatStateBondHolding.quantity > 0)
        .order_by(NatStateBondHolding.id.desc())
    )).all()
    bond_ids = [bond.id for _, bond in bond_rows]
    coupon_earned_by_bond: dict[int, float] = {}
    if bond_ids:
        coupon_rows = await session.execute(
            select(NatBondSettlement.bond_id, func.coalesce(func.sum(NatBondSettlement.amount_rub), 0.0))
            .where(
                NatBondSettlement.company_id == company.id,
                NatBondSettlement.bond_id.in_(bond_ids),
                NatBondSettlement.settlement_type == "COUPON",
                NatBondSettlement.status == "PAID",
            )
            .group_by(NatBondSettlement.bond_id)
        )
        coupon_earned_by_bond = {int(bond_id): round(float(total), 2) for bond_id, total in coupon_rows.all()}
    bonds = []
    for holding, bond in bond_rows:
        invested = round(holding.invested_cash, 2)
        market_value = round(holding.quantity * bond.face_value, 2)
        bonds.append({
            "bond_id": bond.id,
            "title": bond.title,
            "quantity": holding.quantity,
            "invested_cash": invested,
            "market_value": market_value,
            "unrealized_pnl": round(market_value - invested, 2),
            "coupon_rate": bond.coupon_rate,
            "coupon_interval_days": bond.coupon_interval_days,
            "next_coupon_at": bond.next_coupon_at.isoformat() if bond.next_coupon_at else None,
            "maturity_at": bond.maturity_at.isoformat() if bond.maturity_at else None,
            "coupons_earned": coupon_earned_by_bond.get(bond.id, 0.0),
            "status": bond.status,
        })

    instrument_rows = (await session.execute(
        select(NatInstrumentPosition)
        .where(NatInstrumentPosition.company_id == company.id, NatInstrumentPosition.quantity > 0)
        .order_by(NatInstrumentPosition.instrument_code)
    )).scalars().all()
    instruments = []
    for position in instrument_rows:
        rate = await session.scalar(
            select(NatReferenceRateSnapshot)
            .where(NatReferenceRateSnapshot.instrument_code == position.instrument_code)
            .order_by(NatReferenceRateSnapshot.quoted_at.desc(), NatReferenceRateSnapshot.id.desc())
            .limit(1)
        )
        current_price = float(rate.value_rub) * (1 - ReferenceInstrumentService.SPREAD_RATE) if rate else None
        cost_value = round(position.quantity * position.avg_cost_rub, 2)
        market_value = round(position.quantity * current_price, 2) if current_price is not None else None
        instruments.append({
            "instrument_code": position.instrument_code,
            "quantity": position.quantity,
            "avg_cost_rub": position.avg_cost_rub,
            "current_price_rub": round(current_price, 6) if current_price is not None else None,
            "cost_value_rub": cost_value,
            "market_value_rub": market_value,
            "unrealized_pnl_rub": round(market_value - cost_value, 2) if market_value is not None else None,
            "quoted_at": rate.quoted_at.isoformat() if rate else None,
        })

    dividend_payments = [{
        "stock_id": payment.stock_id,
        "issuer_company": issuer.name,
        "shares_count": payment.shares_count,
        "payout_cash": payment.payout_cash,
        "settlement_date": str(payment.settlement_date),
        "paid_at": payment.paid_at.isoformat(),
    } for payment, _, issuer in payment_rows]

    stock_value = round(sum(row["market_value"] for row in stocks), 2)
    bond_value = round(sum(row["market_value"] for row in bonds), 2)
    unrealized_pnl = round(
        sum(row["unrealized_pnl"] for row in stocks) + sum(row["unrealized_pnl"] for row in bonds), 2
    )
    dividends_earned = round(sum(row["payout_cash"] for row in dividend_payments), 2)
    coupons_earned = round(sum(row["coupons_earned"] for row in bonds), 2)
    return {
        "as_of": get_game_now().isoformat(),
        "cash": round(company.cash, 2),
        "summary": {
            "market_value": round(stock_value + bond_value, 2),
            "stocks_market_value": stock_value,
            "bonds_market_value": bond_value,
            "unrealized_pnl": unrealized_pnl,
            "dividends_earned": dividends_earned,
            "coupons_earned": coupons_earned,
        },
        "stocks": stocks,
        "bonds": bonds,
        "instruments": instruments,
        "dividend_payments": dividend_payments,
    }


__all__ = ["router"]
