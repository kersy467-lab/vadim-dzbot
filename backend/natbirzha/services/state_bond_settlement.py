"""Coupon and principal settlement mixin for state bonds."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondSettlement, NatStateBond, NatStateBondHolding
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class StateBondSettlementMixin:
    @classmethod
    async def _ensure_due_rows(cls, session: AsyncSession, bond: NatStateBond, now: datetime) -> None:
        interval = timedelta(minutes=1)
        maturity_at = bond.maturity_at or bond.created_at + timedelta(days=bond.maturity_days)
        next_coupon = bond.next_coupon_at or bond.created_at + interval
        holdings = (await session.execute(
            select(NatStateBondHolding)
            .where(NatStateBondHolding.bond_id == bond.id, NatStateBondHolding.quantity > 0)
            .order_by(NatStateBondHolding.company_id)
            .with_for_update()
        )).scalars().all()
        coupon_end = min(now, maturity_at)
        if next_coupon <= coupon_end:
            coupon_count = int((coupon_end - next_coupon).total_seconds() // interval.total_seconds()) + 1
            for holding in holdings:
                amount = round(
                    bond.face_value * holding.quantity
                    * (bond.coupon_rate / 100.0 / 2.0) / 1_440,
                    12,
                )
                if amount <= 0:
                    continue
                # Catch-up after a long outage must keep one auditable row per
                # minute, without issuing one database round trip per minute.
                # Keep IN clauses below SQLite's bind-parameter limit.
                batch_size = 500
                for batch_start in range(0, coupon_count, batch_size):
                    batch_end = min(batch_start + batch_size, coupon_count)
                    batch_rows = []
                    for offset in range(batch_start, batch_end):
                        coupon_at = next_coupon + interval * offset
                        period = max(
                            1,
                            int((coupon_at - bond.created_at).total_seconds() // 60),
                        )
                        key = f"bond:{bond.id}:coupon-minute:{period}:company:{holding.company_id}"
                        batch_rows.append((key, period, coupon_at))

                    existing_keys = set((await session.scalars(
                        select(NatBondSettlement.operation_key).where(
                            NatBondSettlement.operation_key.in_([row[0] for row in batch_rows])
                        )
                    )).all())
                    for key, period, coupon_at in batch_rows:
                        if key in existing_keys:
                            continue
                        session.add(NatBondSettlement(
                            operation_key=key,
                            bond_id=bond.id,
                            company_id=holding.company_id,
                            settlement_type="COUPON",
                            period_number=period,
                            entitled_quantity=holding.quantity,
                            amount_rub=amount,
                            status="PENDING",
                            due_at=coupon_at,
                            created_at=now,
                        ))
            next_coupon += interval * coupon_count
        bond.next_coupon_at = next_coupon
        if maturity_at <= now:
            bond.is_active = False
            bond.status = "MATURITY_PENDING"
            for holding in holdings:
                key = f"bond:{bond.id}:principal:company:{holding.company_id}"
                exists = await session.scalar(
                    select(NatBondSettlement.id).where(NatBondSettlement.operation_key == key)
                )
                if not exists:
                    session.add(NatBondSettlement(
                        operation_key=key,
                        bond_id=bond.id,
                        company_id=holding.company_id,
                        settlement_type="PRINCIPAL",
                        period_number=0,
                        entitled_quantity=holding.quantity,
                        amount_rub=round(bond.face_value * holding.quantity, 2),
                        status="PENDING",
                        due_at=maturity_at,
                        created_at=now,
                    ))
        await session.flush()

    @classmethod
    async def settle_due(
        cls, session: AsyncSession, now: datetime | None = None, commit: bool = False
    ) -> dict[str, Any]:
        now = now or get_game_now()
        # Cash-moving state services serialize on Treasury first. Once held,
        # settlement locks bonds, their holdings, then recipient companies.
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        bonds = (await session.execute(
            select(NatStateBond)
            .where(NatStateBond.status.notin_(("CLOSED", "BANKRUPT")))
            .order_by(NatStateBond.id)
            .with_for_update()
        )).scalars().all()
        for bond in bonds:
            await cls._ensure_due_rows(session, bond, now)

        pending = (await session.execute(
            select(NatBondSettlement)
            .where(NatBondSettlement.status == "PENDING", NatBondSettlement.due_at <= now)
            .order_by(NatBondSettlement.due_at, NatBondSettlement.id)
            .with_for_update()
        )).scalars().all()
        result = {
            "coupon_payments": 0,
            "coupon_paid_rub": 0.0,
            "maturity_payments": 0,
            "principal_paid_rub": 0.0,
            "coupon_pending": 0,
            "maturity_pending": 0,
        }
        company_ids = sorted({settlement.company_id for settlement in pending})
        companies = (await session.execute(
            select(NatCompany)
            .where(NatCompany.id.in_(company_ids))
            .order_by(NatCompany.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )).scalars().all() if company_ids else []
        company_by_id = {company.id: company for company in companies}

        # Preserve the original chronological allocation when the Treasury is
        # short, while locking each recipient company only once for a backlog
        # that can contain thousands of minute coupon rows.
        payable: list[NatBondSettlement] = []
        remaining_treasury = float(treasury.cash or 0.0)
        for settlement in pending:
            if settlement.company_id not in company_by_id or remaining_treasury < settlement.amount_rub:
                continue
            payable.append(settlement)
            remaining_treasury = round(remaining_treasury - settlement.amount_rub, 8)

        coupon_amounts: dict[int, float] = {}
        principal_amounts: dict[int, float] = {}
        for settlement in payable:
            treasury.cash = round(treasury.cash - settlement.amount_rub, 8)
            settlement.status = "PAID"
            settlement.paid_at = now
            if settlement.settlement_type == "COUPON":
                coupon_amounts[settlement.company_id] = (
                    coupon_amounts.get(settlement.company_id, 0.0) + settlement.amount_rub
                )
                result["coupon_payments"] += 1
                result["coupon_paid_rub"] += settlement.amount_rub
                continue

            principal_amounts[settlement.company_id] = (
                principal_amounts.get(settlement.company_id, 0.0) + settlement.amount_rub
            )
            result["maturity_payments"] += 1
            result["principal_paid_rub"] = round(
                result["principal_paid_rub"] + settlement.amount_rub, 2
            )
            holding = await session.scalar(
                select(NatStateBondHolding).where(
                    NatStateBondHolding.bond_id == settlement.bond_id,
                    NatStateBondHolding.company_id == settlement.company_id,
                ).with_for_update()
            )
            if holding:
                paid_qty = min(holding.quantity, settlement.entitled_quantity)
                old_quantity = holding.quantity
                holding.quantity -= paid_qty
                holding.reserved_quantity = min(holding.reserved_quantity, holding.quantity)
                holding.invested_cash = 0.0 if holding.quantity == 0 else round(
                    holding.invested_cash * holding.quantity / old_quantity, 2
                )
                holding.updated_at = now

        for company_id in sorted(set(coupon_amounts) | set(principal_amounts)):
            company = company_by_id[company_id]
            coupon_amount = coupon_amounts.get(company_id, 0.0)
            dividend_withheld = 0.0
            if coupon_amount > 0:
                dividend_withheld = await DividendService.accrue_cash_inflow(
                    session, company, coupon_amount, now=now
                )
                await CompanyProfitLedgerService.record(
                    session,
                    company.id,
                    now,
                    financial_income=coupon_amount,
                )
            company.cash = round(
                company.cash + coupon_amount + principal_amounts.get(company_id, 0.0)
                - dividend_withheld,
                8,
            )

        treasury.updated_at = now
        await session.flush()
        for bond in bonds:
            if not bond.maturity_at or bond.maturity_at > now:
                continue
            open_count = await session.scalar(
                select(func.count(NatBondSettlement.id)).where(
                    NatBondSettlement.bond_id == bond.id,
                    NatBondSettlement.status == "PENDING",
                )
            )
            if not open_count:
                bond.status = "CLOSED"
                bond.settled_at = now

        result["coupon_pending"] = int(await session.scalar(
            select(func.count(NatBondSettlement.id)).where(
                NatBondSettlement.status == "PENDING",
                NatBondSettlement.settlement_type == "COUPON",
            )
        ) or 0)
        result["maturity_pending"] = int(await session.scalar(
            select(func.count(NatBondSettlement.id)).where(
                NatBondSettlement.status == "PENDING",
                NatBondSettlement.settlement_type == "PRINCIPAL",
            )
        ) or 0)
        result["coupon_paid_rub"] = round(result["coupon_paid_rub"], 2)
        if commit:
            await session.commit()
        return result


__all__ = ["StateBondSettlementMixin"]
