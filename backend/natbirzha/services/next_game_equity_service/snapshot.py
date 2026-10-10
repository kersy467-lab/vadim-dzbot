"""Read-only public share-market and portfolio snapshots for 2.0."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_equity import (
    NatNextGameDividend, NatNextGameDividendPayment, NatNextGameShareHolding,
    NatNextGameShareIssue, NatNextGameShareOrder, NatNextGameShareTrade,
)
from .core import MIN_IPO_COMPANY_LEVEL, NextGameEquityCoreMixin


class NextGameEquitySnapshotMixin:
    @classmethod
    async def snapshot(cls, session: AsyncSession, company: NatNextGameCompany) -> dict[str, Any]:
        issue_rows = (await session.execute(
            select(NatNextGameShareIssue, NatNextGameCompany.name).join(
                NatNextGameCompany, NatNextGameCompany.id == NatNextGameShareIssue.company_id,
            ).where(NatNextGameShareIssue.status == "ACTIVE")
            .order_by(NatNextGameShareIssue.listed_at, NatNextGameShareIssue.id)
        )).all()
        issues = []
        issuer_issue = None
        issue_ids = [int(issue.id) for issue, _issuer_name in issue_rows]
        orders_by_issue: dict[int, list[dict[str, Any]]] = {}
        if issue_ids:
            open_order_rows = (await session.execute(
                select(NatNextGameShareOrder, NatNextGameCompany.name).join(
                    NatNextGameCompany, NatNextGameCompany.id == NatNextGameShareOrder.company_id,
                ).where(
                    NatNextGameShareOrder.issue_id.in_(issue_ids),
                    NatNextGameShareOrder.status == "OPEN",
                    NatNextGameShareOrder.remaining_shares > 0,
                )
            )).all()
            for order, order_company_name in open_order_rows:
                orders_by_issue.setdefault(int(order.issue_id), []).append(
                    NextGameEquityCoreMixin.order_payload(order, order_company_name)
                )
        for issue, issuer_name in issue_rows:
            order_rows = orders_by_issue.get(int(issue.id), [])
            bid = max(
                (row["limit_price"] for row in order_rows if row["side"] == "BUY"), default=None,
            )
            ask = min(
                (row["limit_price"] for row in order_rows if row["side"] == "SELL"), default=None,
            )
            issue_payload = NextGameEquityCoreMixin.issue_payload(issue, issuer_name)
            issue_payload.update({
                "best_bid": bid,
                "best_ask": ask,
                "open_orders": sorted(order_rows, key=lambda row: (
                    0 if row["side"] == "BUY" else 1,
                    -row["limit_price"] if row["side"] == "BUY" else row["limit_price"],
                    row["id"],
                )),
            })
            issues.append(issue_payload)
            if int(issue.company_id) == int(company.id):
                issuer_issue = issue_payload

        holding_rows = (await session.execute(
            select(NatNextGameShareHolding, NatNextGameShareIssue, NatNextGameCompany.name).join(
                NatNextGameShareIssue, NatNextGameShareIssue.id == NatNextGameShareHolding.issue_id,
            ).join(
                NatNextGameCompany, NatNextGameCompany.id == NatNextGameShareIssue.company_id,
            ).where(
                NatNextGameShareHolding.company_id == company.id,
                NatNextGameShareHolding.shares > 0,
            ).order_by(NatNextGameShareIssue.company_id)
        )).all()
        paid_rows = (await session.execute(
            select(NatNextGameDividend.issue_id, NatNextGameDividendPayment.amount).join(
                NatNextGameDividend, NatNextGameDividend.id == NatNextGameDividendPayment.dividend_id,
            ).where(NatNextGameDividendPayment.company_id == company.id)
        )).all()
        dividends_by_issue: dict[int, float] = {}
        for issue_id, amount in paid_rows:
            dividends_by_issue[int(issue_id)] = dividends_by_issue.get(int(issue_id), 0.0) + float(amount)
        positions = []
        for holding, issue, issuer_name in holding_rows:
            price = float(issue.last_price)
            positions.append({
                "issue_id": int(issue.id), "issuer_company_id": int(issue.company_id),
                "issuer_name": str(issuer_name), "shares": int(holding.shares),
                "average_price": round(float(holding.average_price), 4),
                "last_price": round(price, 4),
                "market_value": round(int(holding.shares) * price, 2),
                "dividends_received": round(dividends_by_issue.get(int(issue.id), 0.0), 2),
            })

        own_order_rows = (await session.execute(
            select(NatNextGameShareOrder, NatNextGameCompany.name).join(
                NatNextGameCompany, NatNextGameCompany.id == NatNextGameShareOrder.company_id,
            ).where(
                NatNextGameShareOrder.company_id == company.id,
                NatNextGameShareOrder.status == "OPEN",
            ).order_by(NatNextGameShareOrder.created_at, NatNextGameShareOrder.id)
        )).all()
        own_orders = [NextGameEquityCoreMixin.order_payload(order, name) for order, name in own_order_rows]

        trades = []
        if issue_ids:
            buyer = NatNextGameCompany
            from sqlalchemy.orm import aliased
            seller = aliased(NatNextGameCompany)
            rows = (await session.execute(
                select(NatNextGameShareTrade, buyer.name, seller.name).join(
                    buyer, buyer.id == NatNextGameShareTrade.buyer_company_id,
                ).join(
                    seller, seller.id == NatNextGameShareTrade.seller_company_id,
                ).where(NatNextGameShareTrade.issue_id.in_(issue_ids))
                .order_by(NatNextGameShareTrade.executed_at.desc(), NatNextGameShareTrade.id.desc())
                .limit(24)
            )).all()
            trades = [
                NextGameEquityCoreMixin.trade_payload(trade, buyer_name, seller_name)
                for trade, buyer_name, seller_name in rows
            ]
        dividend_rows = (await session.execute(
            select(NatNextGameDividend, NatNextGameCompany.name).join(
                NatNextGameCompany, NatNextGameCompany.id == NatNextGameDividend.issuer_company_id,
            ).order_by(NatNextGameDividend.created_at.desc(), NatNextGameDividend.id.desc())
            .limit(12)
        )).all()
        dividends = [{
            "issuer_name": str(issuer_name),
            "per_share": round(float(dividend.per_share), 4),
            "total_paid": round(float(dividend.total_paid), 2),
            "created_at": dividend.created_at.isoformat() if dividend.created_at else None,
        } for dividend, issuer_name in dividend_rows]

        facility_count = await session.scalar(
            select(NatNextGameFacility.id).where(
                NatNextGameFacility.company_id == company.id,
            ).limit(1)
        )
        return {
            "eligible_to_ipo": (
                int(company.level) >= MIN_IPO_COMPANY_LEVEL
                and facility_count is not None and issuer_issue is None
            ),
            "ipo_minimum_level": MIN_IPO_COMPANY_LEVEL,
            "own_issue": issuer_issue,
            "issues": issues,
            "positions": positions,
            "my_orders": own_orders,
            "trades": trades,
            "dividends": dividends,
        }


__all__ = ["NextGameEquitySnapshotMixin"]
