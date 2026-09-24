from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondSettlement, NatStateBond, NatStateBondHolding
from backend.natbirzha.models.instruments import (
    NatInstrumentPosition,
    NatInstrumentTrade,
    NatReferenceRateSnapshot,
)
from backend.natbirzha.models.stocks import (
    NatDividend,
    NatDividendPayment,
    NatHourlyDividendPayment,
    NatStock,
    NatStockHolding,
)
from backend.natbirzha.models.state_shares import (
    NatStateShare,
    NatStateShareDividendPayment,
    NatStateShareHolding,
)
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.reference_instrument_service import ReferenceInstrumentService
from backend.natbirzha.services.state_bond_service import StateBondService


router = APIRouter(prefix="/portfolio", tags=["Natbirzha Portfolio"])


async def build_payout_history(session: AsyncSession, company_id: int, limit: int = 100) -> list[dict]:
    """Aggregate immutable payout ledgers into a bounded, newest-first history."""
    limit = max(1, min(int(limit), 100))
    rows: list[dict] = []

    def hour_parts(column):
        return (
            extract("year", column),
            extract("month", column),
            extract("day", column),
            extract("hour", column),
        )

    def append_grouped(result_rows, kind: str, title_for_row):
        for year, month, day, hour, amount, *metadata in result_rows:
            paid_hour = datetime(int(year), int(month), int(day), int(hour))
            rows.append({
                "kind": kind,
                "title": title_for_row(*metadata),
                "payout_cash": round(float(amount or 0.0), 2),
                "paid_at": paid_hour.isoformat(),
                "hour_start": paid_hour.isoformat(),
                "settlement_date": paid_hour.date().isoformat(),
            })

    def order_by_newest(parts):
        return [part.desc() for part in parts]

    # Group minute coupon settlements in SQL before applying LIMIT. Filtering only
    # by the investor company keeps receipts visible after a bond is sold.
    bond_paid_at = NatBondSettlement.paid_at
    bond_hours = hour_parts(bond_paid_at)
    bond_coupon_rows = (await session.execute(
        select(
            *bond_hours,
            func.sum(NatBondSettlement.amount_rub),
        )
        .where(
            NatBondSettlement.company_id == company_id,
            NatBondSettlement.settlement_type == "COUPON",
            NatBondSettlement.status == "PAID",
            bond_paid_at.is_not(None),
        )
        .group_by(*bond_hours)
        .order_by(*order_by_newest(bond_hours))
        .limit(limit)
    )).all()
    append_grouped(bond_coupon_rows, "bond_coupon", lambda: "Купоны по облигациям")

    # Company shares pay hourly; group any duplicate receipts for the same
    # issuer/hour into one history item. Legacy daily-payment rows are included too.
    for payment_model, holder_column, amount_column, paid_column in (
        (NatHourlyDividendPayment, NatHourlyDividendPayment.holder_company_id,
         NatHourlyDividendPayment.payout_cash, NatHourlyDividendPayment.paid_at),
        (NatDividendPayment, NatDividendPayment.holder_company_id,
         NatDividendPayment.payout_cash, NatDividendPayment.paid_at),
    ):
        dividend_hours = hour_parts(paid_column)
        issuer_name = NatCompany.name
        dividend_rows = (await session.execute(
            select(*dividend_hours, func.sum(amount_column), issuer_name)
            .join(NatStock, NatStock.id == payment_model.stock_id)
            .join(NatCompany, NatCompany.id == NatStock.company_id)
            .where(holder_column == company_id, paid_column.is_not(None))
            .group_by(*dividend_hours, issuer_name)
            .order_by(*order_by_newest(dividend_hours))
            .limit(limit)
        )).all()
        append_grouped(dividend_rows, "company_dividend", lambda name: f"Дивиденды: {name}")

    state_paid_at = NatStateShareDividendPayment.paid_at
    state_hours = hour_parts(state_paid_at)
    state_share_rows = (await session.execute(
        select(*state_hours, func.sum(NatStateShareDividendPayment.amount_paid), NatStateShare.title)
        .join(NatStateShare, NatStateShare.id == NatStateShareDividendPayment.share_id)
        .where(
            NatStateShareDividendPayment.company_id == company_id,
            state_paid_at.is_not(None),
        )
        .group_by(*state_hours, NatStateShare.title)
        .order_by(*order_by_newest(state_hours))
        .limit(limit)
    )).all()
    append_grouped(state_share_rows, "state_share_dividend", lambda title: f"Госакции: {title}")

    rows.sort(key=lambda row: row["paid_at"], reverse=True)
    return rows[:limit]


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
    hourly_payment_rows = (await session.execute(
        select(NatHourlyDividendPayment, NatStock, NatCompany)
        .join(NatStock, NatHourlyDividendPayment.stock_id == NatStock.id)
        .join(NatCompany, NatStock.company_id == NatCompany.id)
        .where(NatHourlyDividendPayment.holder_company_id == company.id)
        .order_by(NatHourlyDividendPayment.hour_start.desc(), NatHourlyDividendPayment.id.desc())
    )).all()
    for payment, _, _ in payment_rows:
        payment_totals[payment.stock_id] = round(
            payment_totals.get(payment.stock_id, 0.0) + payment.payout_cash, 2
        )
    latest_hourly_dividends: dict[int, NatHourlyDividendPayment] = {}
    for payment, _, _ in hourly_payment_rows:
        payment_totals[payment.stock_id] = round(
            payment_totals.get(payment.stock_id, 0.0) + payment.payout_cash, 2
        )
        latest_hourly_dividends.setdefault(payment.stock_id, payment)
    latest_dividends: dict[int, NatDividend] = {}
    if stock_ids:
        dividend_rows = (await session.execute(
            select(NatDividend)
            .where(NatDividend.stock_id.in_(stock_ids))
            .order_by(NatDividend.settlement_date.desc(), NatDividend.id.desc())
        )).scalars().all()
        for dividend in dividend_rows:
            latest_dividends.setdefault(dividend.stock_id, dividend)

    current_time = get_game_now()
    next_dividend_at = (
        current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    ).isoformat()
    stocks = []
    for holding, stock, issuer in stock_rows:
        invested = round(holding.shares_count * holding.avg_price, 2)
        market_value = round(holding.shares_count * stock.current_price, 2)
        latest = latest_dividends.get(stock.id)
        latest_hourly = latest_hourly_dividends.get(stock.id)
        stocks.append({
            "stock_id": stock.id,
            "issuer_company": issuer.name,
            "shares_count": holding.shares_count,
            "avg_buy_price": holding.avg_price,
            "current_market_price": stock.current_price,
            "invested_value": invested,
            "market_price": round(float(stock.current_price), 2),
            "market_value": market_value,
            "unrealized_pnl": round(market_value - invested, 2),
            "dividends_earned": payment_totals.get(stock.id, 0.0),
            "latest_dividend_per_share": (
                round(latest_hourly.payout_cash / max(1, latest_hourly.shares_count), 6)
                if latest_hourly else (latest.per_share_amount if latest else 0.0)
            ),
            "latest_dividend_date": (
                latest_hourly.hour_start.isoformat()
                if latest_hourly else (str(latest.settlement_date) if latest else None)
            ),
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
    bond_quotes = {row["id"]: row for row in await StateBondService.list_bonds(session)}
    bonds = []
    for holding, bond in bond_rows:
        invested = round(holding.invested_cash, 2)
        quote = bond_quotes.get(bond.id, {})
        market_price = float(quote.get("market_price", bond.face_value))
        market_value = round(holding.quantity * market_price, 2)
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

    state_share_rows = (await session.execute(
        select(NatStateShareHolding, NatStateShare)
        .join(NatStateShare, NatStateShare.id == NatStateShareHolding.share_id)
        .where(
            NatStateShareHolding.company_id == company.id,
            NatStateShareHolding.quantity > 0,
        )
        .order_by(NatStateShareHolding.id.desc())
    )).all()
    state_share_payment_rows = (await session.execute(
        select(NatStateShareDividendPayment, NatStateShare)
        .join(NatStateShare, NatStateShare.id == NatStateShareDividendPayment.share_id)
        .where(NatStateShareDividendPayment.company_id == company.id)
        .order_by(NatStateShareDividendPayment.settlement_date.desc(), NatStateShareDividendPayment.id.desc())
    )).all()
    state_share_dividends_by_id: dict[int, float] = {}
    state_share_dividend_payments = []
    for payment, share in state_share_payment_rows:
        state_share_dividends_by_id[share.id] = round(
            state_share_dividends_by_id.get(share.id, 0.0) + payment.amount_paid, 2
        )
        state_share_dividend_payments.append({
            "share_id": share.id,
            "title": share.title,
            "shares_count": payment.quantity,
            "payout_cash": payment.amount_paid,
            "settlement_date": str(payment.settlement_date),
            "paid_at": payment.paid_at.isoformat(),
        })
    state_shares = []
    for holding, share in state_share_rows:
        invested = round(float(holding.invested_cash), 2)
        market_value = round(holding.quantity * float(share.issue_price), 2)
        state_shares.append({
            "share_id": share.id,
            "title": share.title,
            "shares_count": holding.quantity,
            "issue_price": share.issue_price,
            "redemption_price": share.issue_price,
            "invested_value": invested,
            "market_value": market_value,
            "unrealized_pnl": round(market_value - invested, 2),
            "dividends_earned": state_share_dividends_by_id.get(share.id, 0.0),
            "dividend_rate_pct": share.dividend_rate_pct,
        })

    instrument_rows = (await session.execute(
        select(NatInstrumentPosition)
        .where(NatInstrumentPosition.company_id == company.id, NatInstrumentPosition.quantity > 0)
        .order_by(NatInstrumentPosition.instrument_code)
    )).scalars().all()
    realized_rows = await session.execute(
        select(
            NatInstrumentTrade.instrument_code,
            func.coalesce(func.sum(NatInstrumentTrade.realized_pnl_rub), 0.0),
        )
        .where(
            NatInstrumentTrade.company_id == company.id,
            NatInstrumentTrade.side == "sell",
        )
        .group_by(NatInstrumentTrade.instrument_code)
    )
    instrument_realized = {
        str(code): round(float(total), 2) for code, total in realized_rows.all()
    }
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
            "realized_pnl_rub": instrument_realized.get(position.instrument_code, 0.0),
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
    dividend_payments.extend({
        "stock_id": payment.stock_id,
        "issuer_company": issuer.name,
        "shares_count": payment.shares_count,
        "payout_cash": payment.payout_cash,
        "settlement_date": str(payment.hour_start.date()),
        "hour_start": payment.hour_start.isoformat(),
        "paid_at": payment.paid_at.isoformat(),
    } for payment, _, issuer in hourly_payment_rows)

    stock_value = round(sum(row["market_value"] for row in stocks), 2)
    bond_value = round(sum(row["market_value"] for row in bonds), 2)
    state_share_value = round(sum(row["market_value"] for row in state_shares), 2)
    instrument_value = round(sum(float(row["market_value_rub"] or 0) for row in instruments), 2)
    unrealized_pnl = round(
        sum(row["unrealized_pnl"] for row in stocks)
        + sum(row["unrealized_pnl"] for row in bonds)
        + sum(row["unrealized_pnl"] for row in state_shares)
        + sum(float(row["unrealized_pnl_rub"] or 0) for row in instruments), 2
    )
    state_share_dividends_earned = round(sum(row["payout_cash"] for row in state_share_dividend_payments), 2)
    dividends_earned = round(sum(row["payout_cash"] for row in dividend_payments) + state_share_dividends_earned, 2)
    coupons_earned = round(float(await session.scalar(
        select(func.coalesce(func.sum(NatBondSettlement.amount_rub), 0.0)).where(
            NatBondSettlement.company_id == company.id,
            NatBondSettlement.settlement_type == "COUPON",
            NatBondSettlement.status == "PAID",
        )
    ) or 0.0), 2)
    realized_pnl = round(sum(instrument_realized.values()), 2)
    payout_history = await build_payout_history(session, company.id)
    return {
        "as_of": get_game_now().isoformat(),
        "cash": round(company.cash, 2),
        "summary": {
            "market_value": round(stock_value + bond_value + instrument_value + state_share_value, 2),
            "stocks_market_value": stock_value,
            "bonds_market_value": bond_value,
            "state_shares_market_value": state_share_value,
            "instruments_market_value": instrument_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl": round(unrealized_pnl + realized_pnl, 2),
            "dividends_earned": dividends_earned,
            "state_share_dividends_earned": state_share_dividends_earned,
            "coupons_earned": coupons_earned,
        },
        "stocks": stocks,
        "bonds": bonds,
        "state_shares": state_shares,
        "instruments": instruments,
        "payout_history": payout_history,
        "dividend_payments": dividend_payments,
        "state_share_dividend_payments": state_share_dividend_payments,
    }


__all__ = ["router"]
