"""Cash dividend settlement between separate 2.0 companies."""

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_equity import (
    NatNextGameDividend, NatNextGameDividendPayment, NatNextGameShareHolding,
    NatNextGameShareIssue,
)
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import NextGameService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NextGameEquityDividendMixin:
    @classmethod
    async def distribute_dividend(
        cls, session: AsyncSession, owner_tg_id: int, per_share: float,
        *, now: datetime | None = None,
    ) -> dict[str, Any]:
        try:
            rate = float(per_share)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Дивиденд на акцию должен быть числом") from exc
        if not isfinite(rate) or rate < 0.01 or rate > 1_000_000:
            raise ValueError("Дивиденд на акцию должен быть от 0,01 до 1 000 000 cash")
        rounded_rate = round(rate, 4)
        if abs(rate - rounded_rate) > 1e-9:
            raise ValueError("Дивиденд можно указать максимум с четырьмя знаками после запятой")
        rate = rounded_rate

        await NextGameMarketService.lock_orderbook(session)
        issuer = await NextGameService._owned_company(session, owner_tg_id)
        issue = await session.scalar(
            select(NatNextGameShareIssue).where(
                NatNextGameShareIssue.company_id == issuer.id,
                NatNextGameShareIssue.status == "ACTIVE",
            ).with_for_update()
        )
        if issue is None:
            raise ValueError("Сначала открой IPO компании")
        rows = (await session.execute(
            select(NatNextGameShareHolding, NatNextGameCompany).join(
                NatNextGameCompany, NatNextGameCompany.id == NatNextGameShareHolding.company_id,
            ).where(
                NatNextGameShareHolding.issue_id == issue.id,
                NatNextGameShareHolding.company_id != issuer.id,
                NatNextGameShareHolding.shares > 0,
            ).order_by(NatNextGameShareHolding.company_id).with_for_update()
        )).all()
        payments = [
            (holding, company, round(int(holding.shares) * rate, 2))
            for holding, company in rows
        ]
        payments = [row for row in payments if row[2] >= 0.01]
        total_paid = round(sum(amount for _holding, _company, amount in payments), 2)
        if total_paid <= 0:
            raise ValueError("У компании пока нет акционеров для выплаты дивидендов")
        if float(issuer.cash) + 1e-8 < total_paid:
            raise ValueError(f"Для выплаты нужно {total_paid:,.2f} cash на балансе компании")

        dividend = NatNextGameDividend(
            issue_id=issue.id, issuer_company_id=issuer.id,
            per_share=rate, total_paid=total_paid, created_at=now or _utcnow(),
        )
        issuer.cash = round(float(issuer.cash) - total_paid, 2)
        session.add(dividend)
        await session.flush()
        payload = []
        for holding, company, amount in payments:
            company.cash = round(float(company.cash) + amount, 2)
            session.add(NatNextGameDividendPayment(
                dividend_id=dividend.id, company_id=company.id,
                shares=int(holding.shares), amount=amount,
            ))
            payload.append({
                "company_id": int(company.id), "company_name": str(company.name),
                "shares": int(holding.shares), "amount": amount,
            })
        await session.flush()
        return {
            "success": True, "dividend_id": int(dividend.id),
            "per_share": rate, "total_paid": total_paid, "payments": payload,
            "company": NextGameService.snapshot_company(issuer),
        }


__all__ = ["NextGameEquityDividendMixin"]
