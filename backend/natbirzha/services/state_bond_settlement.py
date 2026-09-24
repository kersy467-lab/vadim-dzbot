"""Coupon and principal settlement mixin for state bonds."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondSettlement, NatStateBond, NatStateBondHolding
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class StateBondSettlementMixin:
    @classmethod
    async def _ensure_due_rows(cls, session: AsyncSession, bond: NatStateBond, now: datetime) -> None:
        interval = max(1, int(bond.coupon_interval_days or 7))
        maturity_at = bond.maturity_at or bond.created_at + timedelta(days=bond.maturity_days)
        next_coupon = bond.next_coupon_at or bond.created_at + timedelta(days=interval)
        holdings = (await session.execute(
            select(NatStateBondHolding)
            .where(NatStateBondHolding.bond_id == bond.id, NatStateBondHolding.quantity > 0)
            .order_by(NatStateBondHolding.company_id)
            .with_for_update()
        )).scalars().all()
        while next_coupon <= now and next_coupon <= maturity_at:
            period = max(1, int((next_coupon - bond.created_at).days / interval))
            for holding in holdings:
                key = f"bond:{bond.id}:coupon:{period}:company:{holding.company_id}"
                exists = await session.scalar(
                    select(NatBondSettlement.id).where(NatBondSettlement.operation_key == key)
                )
                if exists:
                    continue
                amount = round(
                    bond.face_value * holding.quantity * (bond.coupon_rate / 100.0) * (interval / 365.0), 2
                )
                if amount > 0:
                    session.add(NatBondSettlement(
                        operation_key=key,
                        bond_id=bond.id,
                        company_id=holding.company_id,
                        settlement_type="COUPON",
                        period_number=period,
                        entitled_quantity=holding.quantity,
                        amount_rub=amount,
                        status="PENDING",
                        due_at=next_coupon,
                        created_at=now,
                    ))
            next_coupon += timedelta(days=interval)
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
        for settlement in pending:
            company = await session.scalar(
                select(NatCompany).where(NatCompany.id == settlement.company_id).with_for_update()
                .execution_options(populate_existing=True)
            )
            if not company or treasury.cash < settlement.amount_rub:
                continue
            treasury.cash = round(treasury.cash - settlement.amount_rub, 2)
            company.cash = round(company.cash + settlement.amount_rub, 2)
            settlement.status = "PAID"
            settlement.paid_at = now
            if settlement.settlement_type == "COUPON":
                result["coupon_payments"] += 1
                result["coupon_paid_rub"] = round(result["coupon_paid_rub"] + settlement.amount_rub, 2)
            else:
                result["maturity_payments"] += 1
                result["principal_paid_rub"] = round(result["principal_paid_rub"] + settlement.amount_rub, 2)
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
        if commit:
            await session.commit()
        return result


__all__ = ["StateBondSettlementMixin"]
