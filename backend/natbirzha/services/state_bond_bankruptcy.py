"""Creator action for Treasury-backed state-bond bankruptcy."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import (
    NatBondListing,
    NatBondSettlement,
    NatCreatorAuditLog,
    NatStateBond,
    NatStateBondHolding,
)
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class StateBondBankruptcyMixin:
    @classmethod
    async def declare_bankruptcy(
        cls,
        session: AsyncSession,
        actor_id: int,
        bond_id: int,
        *,
        commit: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Write off a bond's principal and compensate each holder once."""
        now = now or get_game_now()
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True,
        )
        bond = await session.scalar(
            select(NatStateBond)
            .where(NatStateBond.id == bond_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not bond:
            raise ValueError("State bond issue not found.")

        if bond.status == "BANKRUPT":
            prior = (await session.execute(
                select(NatBondSettlement).where(
                    NatBondSettlement.bond_id == bond.id,
                    NatBondSettlement.settlement_type == "BANKRUPTCY",
                    NatBondSettlement.status == "PAID",
                )
            )).scalars().all()
            units = sum(int(row.entitled_quantity) for row in prior)
            paid = round(sum(float(row.amount_rub) for row in prior), 2)
            result = {
                "success": True,
                "bond_id": bond.id,
                "status": "BANKRUPT",
                "already_bankrupt": True,
                "holder_count": len(prior),
                "units_compensated": units,
                "compensation_paid": paid,
                "principal_written_off": round(float(bond.face_value) * units * 0.70, 2),
                "treasury_cash": round(float(treasury.cash), 2),
            }
            if commit:
                await session.commit()
            return result
        if bond.status == "CLOSED":
            raise ValueError("A fully settled bond cannot be declared bankrupt.")

        # Bond lock prevents new offers or fills while open listings are cancelled.
        open_listings = (await session.execute(
            select(NatBondListing)
            .where(NatBondListing.bond_id == bond_id, NatBondListing.status == "OPEN")
            .order_by(NatBondListing.id)
            .with_for_update()
        )).scalars().all()

        # Materialize coupon entitlements already due; never accrue future ones.
        await cls._ensure_due_rows(session, bond, now)
        holdings = (await session.execute(
            select(NatStateBondHolding)
            .where(NatStateBondHolding.bond_id == bond.id, NatStateBondHolding.quantity > 0)
            .order_by(NatStateBondHolding.company_id)
            .with_for_update()
        )).scalars().all()
        company_ids = sorted({int(holding.company_id) for holding in holdings})
        companies = (await session.execute(
            select(NatCompany)
            .where(NatCompany.id.in_(company_ids))
            .order_by(NatCompany.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )).scalars().all() if company_ids else []
        companies_by_id = {company.id: company for company in companies}
        if len(companies_by_id) != len(company_ids):
            raise ValueError("A bond holder company no longer exists.")

        payouts = {
            int(holding.company_id): round(float(bond.face_value) * holding.quantity * 0.30, 2)
            for holding in holdings
        }
        quantities = {int(holding.company_id): int(holding.quantity) for holding in holdings}
        total_units = sum(quantities.values())
        total_paid = round(sum(payouts.values()), 2)
        total_written_off = round(
            sum(float(bond.face_value) * quantity * 0.70 for quantity in quantities.values()), 2,
        )
        if float(treasury.cash) + 1e-9 < total_paid:
            raise ValueError(
                f"Insufficient Treasury cash for exact bankruptcy compensation. "
                f"Required: {total_paid:.2f}; available: {float(treasury.cash):.2f}."
            )

        # Preserve coupons already due, but cancel future coupon and all principal rows.
        pending_rows = (await session.execute(
            select(NatBondSettlement)
            .where(
                NatBondSettlement.bond_id == bond.id,
                NatBondSettlement.status == "PENDING",
            )
            .order_by(NatBondSettlement.id)
            .with_for_update()
        )).scalars().all()
        for settlement in pending_rows:
            if settlement.settlement_type == "PRINCIPAL" or settlement.due_at > now:
                settlement.status = "CANCELLED"

        holdings_by_company = {int(row.company_id): row for row in holdings}
        for listing in open_listings:
            holding = holdings_by_company.get(int(listing.seller_company_id))
            if holding:
                holding.reserved_quantity = max(0, holding.reserved_quantity - listing.quantity)
                holding.updated_at = now
            listing.status = "CANCELLED"
            listing.closed_at = now

        for company_id, quantity in quantities.items():
            holding = holdings_by_company[company_id]
            company = companies_by_id[company_id]
            company.cash = round(float(company.cash) + payouts[company_id], 2)
            holding.quantity = 0
            holding.reserved_quantity = 0
            holding.invested_cash = 0.0
            holding.updated_at = now
            session.add(NatBondSettlement(
                operation_key=f"bond:{bond.id}:bankruptcy:company:{company_id}",
                bond_id=bond.id,
                company_id=company_id,
                settlement_type="BANKRUPTCY",
                period_number=0,
                entitled_quantity=quantity,
                amount_rub=payouts[company_id],
                status="PAID",
                due_at=now,
                paid_at=now,
                created_at=now,
            ))

        treasury.cash = round(float(treasury.cash) - total_paid, 2)
        treasury.updated_at = now
        bond.is_active = False
        bond.status = "BANKRUPT"
        bond.next_coupon_at = None
        session.add(NatCreatorAuditLog(
            actor_id=actor_id,
            action="BOND_BANKRUPTCY",
            target_type="bond",
            target_id=str(bond.id),
            details=(
                f"Выпуск «{bond.title}» признан банкротом: держателям выплачено "
                f"{total_paid:,.2f} cash за {total_units} шт.; списано 70% номинала "
                f"({total_written_off:,.2f} cash). Будущие купоны и погашение прекращены."
            ),
            created_at=now,
        ))
        await session.flush()
        result = {
            "success": True,
            "bond_id": bond.id,
            "status": "BANKRUPT",
            "already_bankrupt": False,
            "holder_count": len(holdings),
            "units_compensated": total_units,
            "compensation_paid": total_paid,
            "principal_written_off": total_written_off,
            "treasury_cash": round(float(treasury.cash), 2),
        }
        if commit:
            await session.commit()
        return result


__all__ = ["StateBondBankruptcyMixin"]
