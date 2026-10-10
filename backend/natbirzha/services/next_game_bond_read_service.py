"""Catalog and owner-scoped portfolios for reserve-bank bonds."""
from datetime import timedelta, timezone
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_bonds import (
    NatNextGameBondSeries, NatNextGameBondHolding, NatNextGameBondListing,
)
from backend.natbirzha.services.next_game_bond_service import NextGameBondService
from backend.natbirzha.services.next_game_service import NextGameService


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


class NextGameBondReadService:
    @staticmethod
    async def snapshot(session, owner, *, now=None):
        await NextGameBondService.settle_all(session, now=now)
        company = await NextGameService._owned_company(session, owner)
        series = (await session.scalars(select(NatNextGameBondSeries).order_by(NatNextGameBondSeries.id))).all()
        holdings = (await session.scalars(select(NatNextGameBondHolding).where(
            NatNextGameBondHolding.company_id == company.id,
            NatNextGameBondHolding.status == "ACTIVE",
        ).order_by(NatNextGameBondHolding.id))).all()
        listing_rows = (await session.execute(select(NatNextGameBondListing, NatNextGameBondHolding,
            NatNextGameCompany.name).join(NatNextGameBondHolding,
            NatNextGameBondHolding.id == NatNextGameBondListing.holding_id).join(NatNextGameCompany,
            NatNextGameCompany.id == NatNextGameBondListing.seller_company_id)
            .where(NatNextGameBondListing.status == "OPEN")
            .order_by(NatNextGameBondListing.unit_price, NatNextGameBondListing.id))).all()
        reserved = {}
        for listing, holding, _name in listing_rows:
            reserved[holding.id] = reserved.get(holding.id, 0) + listing.units
        return {"series": [{"id": row.id, "name": row.name, "issuer": "Резервный банк 2.0",
                "face_price": row.face_price, "daily_rate": row.daily_rate, "term_days": row.term_days}
                for row in series],
            "holdings": [{"id": row.id, "series_id": row.series_id, "units": row.units,
                "free_units": row.units - reserved.get(row.id, 0), "acquired_at": iso(row.acquired_at),
                "matures_at": iso(row.matures_at), "coupon_paid": row.coupon_paid,
                "coupon_remaining": row.coupon_remaining,
                "next_coupon_at": iso(min(row.last_coupon_at + timedelta(hours=1), row.matures_at))}
                for row in holdings],
            "listings": [{"id": row.id, "holding_id": holding.id,
                "seller_company_id": row.seller_company_id, "seller_name": name,
                "series_id": holding.series_id, "units": row.units, "unit_price": row.unit_price,
                "matures_at": iso(holding.matures_at), "mine": row.seller_company_id == company.id}
                for row, holding, name in listing_rows],
            "cash": company.cash, "company_id": company.id}
