"""Read-only API for the persisted rolling 24-hour market-liquidity ranking."""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.models.liquidity import NatLiquiditySnapshot
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.liquidity_service import LiquidityService


router = APIRouter(prefix="/market", tags=["Natbirzha Market Liquidity"])


def _ranking_from_json(sectors: dict, unassigned: dict) -> list[dict]:
    totals: dict[str, dict] = {}
    buckets = [*(sectors or {}).values(), unassigned or {}]
    for bucket in buckets:
        for item_id, detail in (bucket.get("by_item") or {}).items():
            target = totals.setdefault(item_id, {
                "item_id": item_id,
                "buyer_cash_paid": 0.0,
                "seller_cash_received": 0.0,
                "market_fees": 0.0,
                "sale_count": 0,
                "quantity": 0.0,
            })
            for key in ("buyer_cash_paid", "seller_cash_received", "market_fees", "quantity"):
                target[key] += float(detail.get(key, 0.0) or 0.0)
            target["sale_count"] += int(detail.get("sale_count", 0) or 0)

    rows = []
    for item_id, values in totals.items():
        item = CANONICAL_ITEMS.get(item_id, {})
        rows.append({
            **values,
            "name": str(item.get("name", "Неизвестный ресурс")),
            "unit": str(item.get("unit", "шт.")),
        })
    return sorted(rows, key=lambda row: (-row["buyer_cash_paid"], row["item_id"]))


@router.get("/liquidity")
async def get_market_liquidity(
    _company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    now = normalize_dt(get_game_now())
    assert now is not None
    window_end = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
    snapshot = await session.scalar(
        select(NatLiquiditySnapshot)
        .where(NatLiquiditySnapshot.window_end == window_end)
        .limit(1)
    )

    if snapshot is None:
        report = await LiquidityService.aggregate_24h(session, now=window_end)
        window_start = report["window_start"]
        sectors = report["sectors"]
        unassigned = report["unassigned"]
        total_buyer_cash = report["total_buyer_cash_paid"]
        total_seller_cash = report["total_seller_cash_received"]
        total_fees = report["total_market_fees"]
        sale_count = report["sale_count"]
    else:
        window_start = snapshot.window_start
        sectors = snapshot.sectors_json or {}
        unassigned = snapshot.unassigned_json or {}
        total_buyer_cash = float(snapshot.total_buyer_cash_paid or 0.0)
        total_seller_cash = float(snapshot.total_seller_cash_received or 0.0)
        total_fees = float(snapshot.total_market_fees or 0.0)
        sale_count = int(snapshot.sale_count or 0)

    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "refreshed_at": window_end.isoformat(),
        "window_hours": 24,
        "total_buyer_cash_paid": round(total_buyer_cash, 2),
        "total_seller_cash_received": round(total_seller_cash, 2),
        "total_market_fees": round(total_fees, 2),
        "sale_count": sale_count,
        "items": _ranking_from_json(sectors, unassigned),
        "sectors": sectors,
        "coverage": report["coverage"] if snapshot is None else snapshot.coverage_json,
    }


__all__ = ["get_market_liquidity", "router"]
