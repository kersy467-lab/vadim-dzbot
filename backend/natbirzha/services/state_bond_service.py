"""State-bond issuance, holdings and public read models."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import (
    NatBondListing,
    NatCreatorAuditLog,
    NatStateBond,
    NatStateBondHolding,
)
from backend.natbirzha.services.state_bond_secondary import StateBondSecondaryMarketMixin
from backend.natbirzha.services.state_bond_bankruptcy import StateBondBankruptcyMixin
from backend.natbirzha.services.state_bond_settlement import StateBondSettlementMixin
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class StateBondService(StateBondSettlementMixin, StateBondSecondaryMarketMixin, StateBondBankruptcyMixin):
    """Treasury-backed state bonds with settlement and a secondary market."""

    @staticmethod
    def _listing_result(listing: NatBondListing) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        if volume <= 0 or face_value <= 0 or maturity_days <= 0:
            raise ValueError("Volume, face value, and maturity must be positive.")
        if coupon_rate < 0:
            raise ValueError("Coupon rate cannot be negative.")
        if coupon_interval_days is not None and (coupon_interval_days <= 0 or coupon_interval_days > maturity_days):
            raise ValueError("Coupon interval must be positive and not exceed maturity.")
        # Keep the legacy field/API argument for compatibility; coupons now
        # settle every minute at half the configured rate per game day.
        coupon_interval_days = 1
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
            next_coupon_at=now + timedelta(minutes=1),
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
    ) -> dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Bond quantity must be positive.")
        now = now or get_game_now()
        # Settle all elapsed coupon periods before adding a new holder. This
        # prevents a buyer from collecting minutes that elapsed before purchase.
        await cls.settle_due(session, now=now, commit=False)
        # Cash-moving state instruments all lock Treasury before companies to
        # keep the shared Treasury/holder lock order consistent.
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if not company:
            raise ValueError("Company not found.")
        from backend.natbirzha.services.state_credit_service import StateCreditService
        if await StateCreditService.has_open_credit(session, company.id):
            raise ValueError("Repay the open state credit before buying state bonds.")
        bond = await session.scalar(select(NatStateBond).where(NatStateBond.id == bond_id).with_for_update())
        if not bond or not bond.is_active or (bond.maturity_at and now >= bond.maturity_at):
            raise ValueError("Active bond issue not found.")
        if bond.remaining_volume < quantity:
            raise ValueError(
                f"Insufficient bond supply. Remaining: {bond.remaining_volume}, requested: {quantity}."
            )
        from backend.natbirzha.services.sabotage_service import SabotageService
        bond_mult = SabotageService.get_bond_price_multiplier()
        total_cost = round(float(bond.face_value) * quantity * bond_mult, 2)
        if company.cash < total_cost:
            raise ValueError(f"Insufficient cash. Required: {total_cost}, Available: {company.cash}")
        holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == bond.id,
            NatStateBondHolding.company_id == company.id,
        ).with_for_update())
        if not holding:
            holding = NatStateBondHolding(
                bond_id=bond.id,
                company_id=company.id,
                quantity=0,
                reserved_quantity=0,
                invested_cash=0.0,
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

    @staticmethod
    async def holdings(session: AsyncSession, company_id: int) -> list[dict[str, Any]]:
        result = await session.execute(
            select(NatStateBondHolding, NatStateBond)
            .join(NatStateBond, NatStateBondHolding.bond_id == NatStateBond.id)
            .where(NatStateBondHolding.company_id == company_id)
            .order_by(NatStateBondHolding.id.desc())
        )
        return [{
            "bond_id": bond.id,
            "title": bond.title,
            "quantity": holding.quantity,
            "reserved_quantity": holding.reserved_quantity,
            "available_quantity": holding.quantity - holding.reserved_quantity,
            "invested_cash": holding.invested_cash,
            "face_value": bond.face_value,
            "coupon_rate": bond.coupon_rate,
            "coupon_interval_days": bond.coupon_interval_days,
            "maturity_days": bond.maturity_days,
            "maturity_at": bond.maturity_at.isoformat() if bond.maturity_at else None,
            "status": bond.status,
        } for holding, bond in result.all()]

    @staticmethod
    async def list_bonds(session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(select(NatStateBond).order_by(NatStateBond.created_at.desc()))
        bonds = []
        for bond in result.scalars().all():
            listing_rows = (await session.execute(
                select(NatBondListing)
                .where(NatBondListing.bond_id == bond.id)
                .order_by(NatBondListing.created_at.asc(), NatBondListing.id.asc())
            )).scalars().all()
            filled = [row for row in listing_rows if row.status == "FILLED"]
            open_asks = [row for row in listing_rows if row.status == "OPEN"]
            last_market_price = filled[-1].unit_price if filled else float(bond.face_value)
            best_ask = min((row.unit_price for row in open_asks), default=None)
            market_price = float(best_ask if best_ask is not None else last_market_price)
            history = [{"timestamp": bond.created_at.isoformat(), "price": bond.face_value}]
            history.extend({
                "timestamp": (row.closed_at or row.created_at).isoformat(),
                "price": row.unit_price,
            } for row in filled)
            asks_by_price: dict[float, int] = {}
            for row in open_asks:
                asks_by_price[float(row.unit_price)] = asks_by_price.get(float(row.unit_price), 0) + int(row.quantity)
            orderbook_asks = [
                {"price": price, "quantity": asks_by_price[price]}
                for price in sorted(asks_by_price)[:12]
            ]
            bonds.append({
                "id": bond.id,
                "title": bond.title,
                "total_volume": bond.total_volume,
                "remaining_volume": bond.remaining_volume,
                "face_value": bond.face_value,
                "coupon_rate": bond.coupon_rate,
                "coupon_interval_days": bond.coupon_interval_days,
                "maturity_days": bond.maturity_days,
                "maturity_at": bond.maturity_at.isoformat() if bond.maturity_at else None,
                "next_coupon_at": bond.next_coupon_at.isoformat() if bond.next_coupon_at else None,
                "purpose": bond.purpose,
                "is_active": bond.is_active,
                "status": bond.status,
                "created_at": bond.created_at.isoformat(),
                "market_price": round(market_price, 2),
                "best_ask": round(best_ask, 2) if best_ask is not None else None,
                "orderbook_asks": orderbook_asks,
                "history": history,
            })
        return bonds


__all__ = ["StateBondService"]
