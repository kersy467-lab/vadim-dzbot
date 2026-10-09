"""Recover stock valuation anchors written by the previous rebirth formula."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock, NatStockPriceSnapshot
from backend.natbirzha.services.rebirth_valuation import recover_rebirth_anchor


async def restore_legacy_rebirth_anchor(
    session: AsyncSession, stock: NatStock, company: NatCompany
) -> None:
    if stock.rebirth_valuation_anchor is not None or not company.last_rebirth_at:
        return
    scale = float(stock.rebirth_valuation_scale or 1.0)
    if int(company.rebirth_count or 0) <= 0 or abs(scale - 1.0) <= 1e-9:
        return

    snapshot = await session.scalar(
        select(NatStockPriceSnapshot)
        .where(
            NatStockPriceSnapshot.stock_id == stock.id,
            NatStockPriceSnapshot.captured_at >= company.last_rebirth_at,
        )
        .order_by(NatStockPriceSnapshot.captured_at.asc(), NatStockPriceSnapshot.id.asc())
        .limit(1)
    )
    if snapshot is None:
        return

    anchor, baseline = recover_rebirth_anchor(
        first_price=snapshot.price,
        total_shares=stock.total_shares,
        legacy_scale=scale,
    )
    stock.rebirth_valuation_anchor = anchor
    stock.rebirth_base_valuation = baseline
    stock.rebirth_valuation_scale = 1.0


__all__ = ["restore_legacy_rebirth_anchor"]
