from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import func, select
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


class StateBondService:
    """State bonds with treasury-backed settlement and a reserved secondary market."""

    @staticmethod
    def _listing_result(listing: NatBondListing) -> Dict[str, Any]:
        return {
            "success": True,
            "listing_id": listing.id,
            "bond_id": listing.bond_id,
            "seller_company_id": listing.seller_company_id,
            "buyer_company_id": listing.buyer_company_id,
            "quantity": listing.quantity,
            "unit_price": listing.unit_price,
            "total_cost": round(listing.quantity * listing.unit_price, 2),
            "status": listing.status,
        }

    @classmethod
    async def issue(
        cls,
        session: AsyncSession,
        actor_id: int,
        title: str,
        volume: int,
        face_value: float,
        coupon_rate: float,
        maturity_days: int,
        purpose: str,
        commit: bool = True,
        coupon_interval_days: int | None = None,
        now: datetime | None = None,
    ) -> Dict[str, Any]:
        if volume <= 0 or face_value <= 0 or maturity_days <= 0:
            raise ValueError("Volume, face value, and maturity must be positive.")
        if coupon_rate < 0:
            raise ValueError("Coupon rate cannot be negative.")
        # New issues pay every 24 hours. The optional interval remains for
        # special issues and backwards-compatible admin tools.
        coupon_interval_days = min(1, maturity_days) if coupon_interval_days is None else coupon_interval_days
        if coupon_interval_days <= 0 or coupon_interval_days > maturity_days:
            raise ValueError("Coupon interval must be positive and not exceed maturity.")
        treasury = await StateTreasuryService.get_or_create(session, commit=False)
        now = now or get_game_now()
        bond = NatStateBond(
            title=title,
            total_volume=volume,
            remaining_volume=volume,
            face_value=face_value,
            coupon_rate=coupon_rate,
            maturity_days=maturity_days,
            coupon_interval_days=coupon_interval_days,
            purpose=purpose,
            actor_id=actor_id,
            is_active=True,
            status="OFFERING",
            next_coupon_at=now + timedelta(days=coupon_interval_days),
            maturity_at=now + timedelta(days=maturity_days),
            created_at=now,
        )
        session.add(bond)
        issued_face_value = round(volume * face_value, 2)
        session.add(NatCreatorAuditLog(
            actor_id=actor_id,
            action="BOND_ISSUANCE",
            target_type="bond",
            target_id=title,
            details=f"Выпуск {volume} шт. номиналом {issued_face_value} cash. Цель: {purpose}",
            created_at=now,
        ))
        await session.flush()
        result = {
            "success": True,
            "bond_id": bond.id,
            "title": bond.title,
            "issued_face_value": issued_face_value,
            "raised_funds": 0.0,
            "treasury_cash": treasury.cash,
            "next_coupon_at": bond.next_coupon_at.isoformat(),
            "maturity_at": bond.maturity_at.isoformat(),
        }
        if commit:
            await session.commit()
        return result

    @classmethod
    async def buy(
        cls,
        session: AsyncSession,
        company: NatCompany,
        bond_id: int,
        quantity: int,
        commit: bool = True,
        now: datetime | None = None,
    ) -> Dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Bond quantity must be positive.")
        now = now or get_game_now()
        company = await session.scalar(select(NatCompany).where(NatCompany.id == company.id).with_for_update())
        if not company:
            raise ValueError("Company not found.")
        bond = await session.scalar(select(NatStateBond).where(NatStateBond.id == bond_id).with_for_update())
        if not bond or not bond.is_active or (bond.maturity_at and now >= bond.maturity_at):
            raise ValueError("Active bond issue not found.")
        if bond.remaining_volume < quantity:
            raise ValueError(f"Insufficient bond supply. Remaining: {bond.remaining_volume}, requested: {quantity}.")
        total_cost = round(float(bond.face_value) * quantity, 2)
        if company.cash < total_cost:
            raise ValueError(f"Insufficient cash. Required: {total_cost}, Available: {company.cash}")
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == bond.id,
            NatStateBondHolding.company_id == company.id,
        ).with_for_update())
        if not holding:
            holding = NatStateBondHolding(
                bond_id=bond.id, company_id=company.id, quantity=0, reserved_quantity=0, invested_cash=0.0
            )
            session.add(holding)
        company.cash = round(company.cash - total_cost, 2)
        treasury.cash = round(treasury.cash + total_cost, 2)
        treasury.updated_at = now
        bond.remaining_volume -= quantity
        bond.status = "ACTIVE"
        if bond.remaining_volume <= 0:
            bond.remaining_volume = 0
            bond.is_active = False
        holding.quantity += quantity
        holding.invested_cash = round(holding.invested_cash + total_cost, 2)
        holding.updated_at = now
        await session.flush()
        result = {
            "success": True,
            "bond_id": bond.id,
            "quantity_bought": quantity,
            "total_cost": total_cost,
            "remaining_volume": bond.remaining_volume,
            "remaining_cash": company.cash,
            "treasury_cash": treasury.cash,
        }
        if commit:
            await session.commit()
        return result

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
                exists = await session.scalar(select(NatBondSettlement.id).where(NatBondSettlement.operation_key == key))
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
                exists = await session.scalar(select(NatBondSettlement.id).where(NatBondSettlement.operation_key == key))
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
    ) -> Dict[str, Any]:
        now = now or get_game_now()
        bonds = (await session.execute(
            select(NatStateBond).where(NatStateBond.status != "CLOSED").order_by(NatStateBond.id).with_for_update()
        )).scalars().all()
        for bond in bonds:
            await cls._ensure_due_rows(session, bond, now)
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        pending = (await session.execute(
            select(NatBondSettlement)
            .where(NatBondSettlement.status == "PENDING", NatBondSettlement.due_at <= now)
            .order_by(NatBondSettlement.due_at, NatBondSettlement.id)
            .with_for_update()
        )).scalars().all()
        result = {
            "coupon_payments": 0, "coupon_paid_rub": 0.0,
            "maturity_payments": 0, "principal_paid_rub": 0.0,
            "coupon_pending": 0, "maturity_pending": 0,
        }
        for settlement in pending:
            company = await session.scalar(select(NatCompany).where(
                NatCompany.id == settlement.company_id
            ).with_for_update())
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
                holding = await session.scalar(select(NatStateBondHolding).where(
                    NatStateBondHolding.bond_id == settlement.bond_id,
                    NatStateBondHolding.company_id == settlement.company_id,
                ).with_for_update())
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
            open_count = await session.scalar(select(func.count(NatBondSettlement.id)).where(
                NatBondSettlement.bond_id == bond.id,
                NatBondSettlement.status == "PENDING",
            ))
            if not open_count:
                bond.status = "CLOSED"
                bond.settled_at = now
        result["coupon_pending"] = int(await session.scalar(select(func.count(NatBondSettlement.id)).where(
            NatBondSettlement.status == "PENDING", NatBondSettlement.settlement_type == "COUPON"
        )) or 0)
        result["maturity_pending"] = int(await session.scalar(select(func.count(NatBondSettlement.id)).where(
            NatBondSettlement.status == "PENDING", NatBondSettlement.settlement_type == "PRINCIPAL"
        )) or 0)
        if commit:
            await session.commit()
        return result

    @classmethod
    async def create_listing(
        cls, session: AsyncSession, seller_company_id: int, bond_id: int,
        quantity: int, unit_price: float, operation_key: str,
        now: datetime | None = None, commit: bool = False,
    ) -> Dict[str, Any]:
        if quantity <= 0 or unit_price <= 0:
            raise ValueError("Quantity and price must be positive.")
        now = now or get_game_now()
        existing = await session.scalar(select(NatBondListing).where(NatBondListing.operation_key == operation_key))
        if existing:
            if (existing.seller_company_id, existing.bond_id, existing.quantity, existing.unit_price) != (
                seller_company_id, bond_id, quantity, unit_price
            ):
                raise ValueError("Operation key was already used for a different listing.")
            return cls._listing_result(existing)
        bond = await session.scalar(select(NatStateBond).where(NatStateBond.id == bond_id).with_for_update())
        if not bond or bond.status in ("MATURITY_PENDING", "CLOSED") or (bond.maturity_at and now >= bond.maturity_at):
            raise ValueError("Bond is not available for secondary trading.")
        holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == bond_id,
            NatStateBondHolding.company_id == seller_company_id,
        ).with_for_update())
        if not holding or holding.quantity - holding.reserved_quantity < quantity:
            raise ValueError("Insufficient unreserved bond holdings.")
        holding.reserved_quantity += quantity
        holding.updated_at = now
        listing = NatBondListing(
            operation_key=operation_key, bond_id=bond_id, seller_company_id=seller_company_id,
            quantity=quantity, unit_price=round(unit_price, 2), status="OPEN", created_at=now,
        )
        session.add(listing)
        await session.flush()
        result = cls._listing_result(listing)
        if commit:
            await session.commit()
        return result

    @classmethod
    async def buy_listing(
        cls, session: AsyncSession, buyer_company_id: int, listing_id: int,
        operation_key: str, now: datetime | None = None, commit: bool = False,
    ) -> Dict[str, Any]:
        now = now or get_game_now()
        replay = await session.scalar(select(NatBondListing).where(NatBondListing.filled_operation_key == operation_key))
        if replay:
            if replay.buyer_company_id != buyer_company_id or replay.id != listing_id:
                raise ValueError("Operation key was already used for a different purchase.")
            return cls._listing_result(replay)
        listing = await session.scalar(select(NatBondListing).where(NatBondListing.id == listing_id).with_for_update())
        if not listing or listing.status != "OPEN":
            raise ValueError("Open bond listing not found.")
        if listing.seller_company_id == buyer_company_id:
            raise ValueError("A company cannot buy its own listing.")
        bond = await session.scalar(select(NatStateBond).where(NatStateBond.id == listing.bond_id).with_for_update())
        if not bond or bond.status in ("MATURITY_PENDING", "CLOSED") or (bond.maturity_at and now >= bond.maturity_at):
            raise ValueError("Bond has reached maturity.")
        companies = (await session.execute(
            select(NatCompany)
            .where(NatCompany.id.in_(sorted((buyer_company_id, listing.seller_company_id))))
            .order_by(NatCompany.id).with_for_update()
        )).scalars().all()
        by_id = {company.id: company for company in companies}
        buyer, seller = by_id.get(buyer_company_id), by_id.get(listing.seller_company_id)
        if not buyer or not seller:
            raise ValueError("Buyer or seller company not found.")
        total_cost = round(listing.quantity * listing.unit_price, 2)
        if buyer.cash < total_cost:
            raise ValueError("Insufficient cash.")
        seller_holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == listing.bond_id,
            NatStateBondHolding.company_id == listing.seller_company_id,
        ).with_for_update())
        if not seller_holding or seller_holding.reserved_quantity < listing.quantity or seller_holding.quantity < listing.quantity:
            raise ValueError("Reserved seller holdings are inconsistent.")
        buyer_holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == listing.bond_id,
            NatStateBondHolding.company_id == buyer_company_id,
        ).with_for_update())
        if not buyer_holding:
            buyer_holding = NatStateBondHolding(
                bond_id=listing.bond_id, company_id=buyer_company_id,
                quantity=0, reserved_quantity=0, invested_cash=0.0,
            )
            session.add(buyer_holding)
        cost_basis = round(seller_holding.invested_cash * listing.quantity / seller_holding.quantity, 2)
        buyer.cash = round(buyer.cash - total_cost, 2)
        seller.cash = round(seller.cash + total_cost, 2)
        seller_holding.quantity -= listing.quantity
        seller_holding.reserved_quantity -= listing.quantity
        seller_holding.invested_cash = round(max(0.0, seller_holding.invested_cash - cost_basis), 2)
        buyer_holding.quantity += listing.quantity
        buyer_holding.invested_cash = round(buyer_holding.invested_cash + total_cost, 2)
        seller_holding.updated_at = buyer_holding.updated_at = now
        listing.status = "FILLED"
        listing.buyer_company_id = buyer_company_id
        listing.filled_operation_key = operation_key
        listing.closed_at = now
        await session.flush()
        result = cls._listing_result(listing)
        if commit:
            await session.commit()
        return result

    @classmethod
    async def cancel_listing(
        cls, session: AsyncSession, seller_company_id: int, listing_id: int,
        now: datetime | None = None, commit: bool = False,
    ) -> Dict[str, Any]:
        now = now or get_game_now()
        listing = await session.scalar(select(NatBondListing).where(NatBondListing.id == listing_id).with_for_update())
        if not listing or listing.status != "OPEN" or listing.seller_company_id != seller_company_id:
            raise ValueError("Open bond listing not found.")
        holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == listing.bond_id,
            NatStateBondHolding.company_id == seller_company_id,
        ).with_for_update())
        if holding:
            holding.reserved_quantity = max(0, holding.reserved_quantity - listing.quantity)
            holding.updated_at = now
        listing.status = "CANCELLED"
        listing.closed_at = now
        await session.flush()
        result = cls._listing_result(listing)
        if commit:
            await session.commit()
        return result

    @staticmethod
    async def listings(session: AsyncSession) -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(NatBondListing).order_by(NatBondListing.created_at.desc(), NatBondListing.id.desc())
        )).scalars().all()
        return [StateBondService._listing_result(row) for row in rows]

    @staticmethod
    async def holdings(session: AsyncSession, company_id: int) -> List[Dict[str, Any]]:
        result = await session.execute(
            select(NatStateBondHolding, NatStateBond)
            .join(NatStateBond, NatStateBondHolding.bond_id == NatStateBond.id)
            .where(NatStateBondHolding.company_id == company_id)
            .order_by(NatStateBondHolding.id.desc())
        )
        return [{
            "bond_id": bond.id, "title": bond.title,
            "quantity": holding.quantity, "reserved_quantity": holding.reserved_quantity,
            "available_quantity": holding.quantity - holding.reserved_quantity,
            "invested_cash": holding.invested_cash, "face_value": bond.face_value,
            "coupon_rate": bond.coupon_rate, "coupon_interval_days": bond.coupon_interval_days,
            "maturity_days": bond.maturity_days,
            "maturity_at": bond.maturity_at.isoformat() if bond.maturity_at else None,
            "status": bond.status,
        } for holding, bond in result.all()]

    @staticmethod
    async def list_bonds(session: AsyncSession) -> List[Dict[str, Any]]:
        result = await session.execute(select(NatStateBond).order_by(NatStateBond.created_at.desc()))
        bonds = []
        for bond in result.scalars().all():
            listing_rows = (await session.execute(
                select(NatBondListing)
                .where(NatBondListing.bond_id == bond.id)
                .order_by(NatBondListing.created_at.asc(), NatBondListing.id.asc())
            )).scalars().all()
            bonds.append({
                "id": bond.id, "title": bond.title, "total_volume": bond.total_volume,
                "remaining_volume": bond.remaining_volume, "face_value": bond.face_value,
                "coupon_rate": bond.coupon_rate, "coupon_interval_days": bond.coupon_interval_days,
                "maturity_days": bond.maturity_days,
                "maturity_at": bond.maturity_at.isoformat() if bond.maturity_at else None,
                "next_coupon_at": bond.next_coupon_at.isoformat() if bond.next_coupon_at else None,
                "purpose": bond.purpose, "is_active": bond.is_active, "status": bond.status,
                "created_at": bond.created_at.isoformat(),
                "history": [
                    {"timestamp": listing.created_at.isoformat(), "price": listing.unit_price}
                    for listing in listing_rows
                ],
            })
        return bonds


__all__ = ["StateBondService"]
