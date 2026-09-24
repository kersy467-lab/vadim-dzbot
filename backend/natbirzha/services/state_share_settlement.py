"""Treasury-wide prorated daily dividend settlement for state share issues."""

from datetime import date
from decimal import Decimal, ROUND_DOWN
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, get_game_today
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.state_shares import (
    NatStateShare,
    NatStateShareDailySettlement,
    NatStateShareDividendPayment,
    NatStateShareHolding,
)
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class StateShareSettlementMixin:
    """Settle all issue obligations against one shared Treasury balance."""

    @staticmethod
    def _replayed_settlement(settlement: NatStateShareDailySettlement) -> dict[str, Any]:
        return {
            "status": "already_settled",
            "date": str(settlement.settlement_date),
            "total_due": round(settlement.total_due, 2),
            "total_paid": round(settlement.total_paid, 2),
            "proration_ratio": settlement.proration_ratio,
        }

    @staticmethod
    async def settle_daily_dividends(
        session: AsyncSession,
        settlement_date: date | None = None,
        *,
        commit: bool = True,
    ) -> dict[str, Any]:
        settlement_date = settlement_date or get_game_today()
        existing = await session.scalar(select(NatStateShareDailySettlement).where(
            NatStateShareDailySettlement.settlement_date == settlement_date
        ))
        if existing:
            return StateShareSettlementMixin._replayed_settlement(existing)

        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        # The Treasury lock serializes settlements, buys, and redemptions. Recheck
        # the date after acquiring it so concurrent scheduler workers replay.
        existing = await session.scalar(select(NatStateShareDailySettlement).where(
            NatStateShareDailySettlement.settlement_date == settlement_date
        ))
        if existing:
            return StateShareSettlementMixin._replayed_settlement(existing)

        rows = await session.execute(
            select(NatStateShareHolding, NatStateShare)
            .join(NatStateShare, NatStateShare.id == NatStateShareHolding.share_id)
            .where(
                NatStateShareHolding.quantity > 0,
                NatStateShare.projected_annual_profit > 0,
                NatStateShare.dividend_rate_pct > 0,
            )
            .order_by(NatStateShare.id, NatStateShareHolding.company_id)
        )
        holding_share_rows = rows.all()
        company_ids = sorted({int(holding.company_id) for holding, _share in holding_share_rows})
        companies = (await session.execute(
            select(NatCompany)
            .where(NatCompany.id.in_(company_ids))
            .order_by(NatCompany.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )).scalars().all() if company_ids else []
        companies_by_id = {company.id: company for company in companies}

        obligations: list[tuple[NatStateShareHolding, NatStateShare, Decimal]] = []
        for holding, share in holding_share_rows:
            if holding.company_id not in companies_by_id:
                continue
            due = (
                Decimal(str(share.projected_annual_profit))
                * Decimal(str(share.dividend_rate_pct))
                / Decimal(100)
                * Decimal(holding.quantity)
                / Decimal(share.total_volume)
                / Decimal(365)
            )
            if due > 0:
                obligations.append((holding, share, due))

        total_due = sum((item[2] for item in obligations), Decimal(0))
        treasury_before = max(Decimal(0), Decimal(str(treasury.cash)))
        ratio = min(Decimal(1), treasury_before / total_due) if total_due else Decimal(1)
        target_cents = int((min(total_due, treasury_before) * 100).to_integral_value(rounding=ROUND_DOWN))
        exact_cents = [item[2] * ratio * 100 for item in obligations]
        payouts = [int(value.to_integral_value(rounding=ROUND_DOWN)) for value in exact_cents]
        remainder = target_cents - sum(payouts)
        priority = sorted(
            range(len(obligations)),
            key=lambda index: (
                -(exact_cents[index] - payouts[index]),
                obligations[index][1].id,
                obligations[index][0].company_id,
            ),
        )
        for index in priority[:remainder]:
            payouts[index] += 1

        paid_total = Decimal(sum(payouts)) / 100
        settlement = NatStateShareDailySettlement(
            operation_key=f"state-share-dividend:{settlement_date.isoformat()}",
            settlement_date=settlement_date,
            total_due=float(total_due),
            total_paid=float(paid_total),
            proration_ratio=float(ratio),
            treasury_cash_before=float(treasury_before),
            treasury_cash_after=round(float(treasury_before - paid_total), 2),
        )
        session.add(settlement)
        await session.flush()

        payment_count = 0
        for index, (holding, share, due) in enumerate(obligations):
            company = companies_by_id[holding.company_id]
            paid = Decimal(payouts[index]) / 100
            reinvested_dividend = await DividendService.accrue_cash_inflow(
                session, company, float(paid), now=get_game_now()
            )
            company.cash = round(
                float(company.cash) + float(paid) - reinvested_dividend, 2
            )
            holding.dividends_earned = round(float(holding.dividends_earned) + float(paid), 2)
            session.add(NatStateShareDividendPayment(
                operation_key=f"state-share-dividend:{settlement_date.isoformat()}:{share.id}:{company.id}",
                settlement_id=settlement.id,
                share_id=share.id,
                company_id=company.id,
                quantity=holding.quantity,
                settlement_date=settlement_date,
                amount_due=float(due),
                amount_paid=float(paid),
                paid_at=get_game_now(),
            ))
            payment_count += 1

        treasury.cash = round(float(treasury_before - paid_total), 2)
        treasury.updated_at = get_game_now()
        await session.flush()
        result = {
            "status": "settled",
            "date": str(settlement_date),
            "payment_count": payment_count,
            "total_due": round(float(total_due), 2),
            "total_paid": round(float(paid_total), 2),
            "proration_ratio": round(float(ratio), 8),
            "treasury_cash": round(float(treasury.cash), 2),
        }
        if commit:
            await session.commit()
        return result


__all__ = ["StateShareSettlementMixin"]
