"""Reserved secondary market mixin for state bonds."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatBondListing, NatStateBond, NatStateBondHolding


class StateBondSecondaryMarketMixin:
    @classmethod
    async def create_listing(
        cls, session: AsyncSession, seller_company_id: int, bond_id: int,
        quantity: int, unit_price: float, operation_key: str,
        now: datetime | None = None, commit: bool = False,
    ) -> dict[str, Any]:
        if quantity <= 0 or unit_price <= 0:
            raise ValueError("Quantity and price must be positive.")
        now = now or get_game_now()
        existing = await session.scalar(
            select(NatBondListing).where(NatBondListing.operation_key == operation_key)
        )
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
            operation_key=operation_key,
            bond_id=bond_id,
            seller_company_id=seller_company_id,
            quantity=quantity,
            unit_price=round(unit_price, 2),
            status="OPEN",
            created_at=now,
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
    ) -> dict[str, Any]:
        now = now or get_game_now()
        replay = await session.scalar(
            select(NatBondListing).where(NatBondListing.filled_operation_key == operation_key)
        )
        if replay:
            if replay.buyer_company_id != buyer_company_id or replay.id != listing_id:
                raise ValueError("Operation key was already used for a different purchase.")
            return cls._listing_result(replay)
        listing = await session.scalar(
            select(NatBondListing).where(NatBondListing.id == listing_id).with_for_update()
        )
        if not listing or listing.status != "OPEN":
            raise ValueError("Open bond listing not found.")
        if listing.seller_company_id == buyer_company_id:
            raise ValueError("A company cannot buy its own listing.")
        bond = await session.scalar(
            select(NatStateBond).where(NatStateBond.id == listing.bond_id).with_for_update()
        )
        if not bond or bond.status in ("MATURITY_PENDING", "CLOSED") or (bond.maturity_at and now >= bond.maturity_at):
            raise ValueError("Bond has reached maturity.")
        companies = (await session.execute(
            select(NatCompany)
            .where(NatCompany.id.in_(sorted((buyer_company_id, listing.seller_company_id))))
            .order_by(NatCompany.id)
            .with_for_update()
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
        if (
            not seller_holding
            or seller_holding.reserved_quantity < listing.quantity
            or seller_holding.quantity < listing.quantity
        ):
            raise ValueError("Reserved seller holdings are inconsistent.")
        buyer_holding = await session.scalar(select(NatStateBondHolding).where(
            NatStateBondHolding.bond_id == listing.bond_id,
            NatStateBondHolding.company_id == buyer_company_id,
        ).with_for_update())
        if not buyer_holding:
            buyer_holding = NatStateBondHolding(
                bond_id=listing.bond_id,
                company_id=buyer_company_id,
                quantity=0,
                reserved_quantity=0,
                invested_cash=0.0,
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
    ) -> dict[str, Any]:
        now = now or get_game_now()
        listing = await session.scalar(
            select(NatBondListing).where(NatBondListing.id == listing_id).with_for_update()
        )
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

    @classmethod
    async def listings(cls, session: AsyncSession) -> list[dict[str, Any]]:
        rows = (await session.execute(
            select(NatBondListing).order_by(NatBondListing.created_at.desc(), NatBondListing.id.desc())
        )).scalars().all()
        return [cls._listing_result(row) for row in rows]


__all__ = ["StateBondSecondaryMarketMixin"]
