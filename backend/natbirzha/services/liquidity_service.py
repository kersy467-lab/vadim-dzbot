"""Aggregate paid sale receipts without counting mirrored financial ledgers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import INDUSTRIES
from backend.natbirzha.config import get_game_now, get_game_tz, normalize_dt
from backend.natbirzha.models.city_orders import NatCityOrderDelivery
from backend.natbirzha.models.economy_metrics import NatEconomyEvent
from backend.natbirzha.models.liquidity import NatLiquiditySnapshot
from backend.natbirzha.models.market import NatMarketTrade
from backend.natbirzha.models.player_deals import NatSupplyDealSettlement


def _empty_bucket() -> dict[str, Any]:
    return {
        "seller_cash_received": 0.0,
        "buyer_cash_paid": 0.0,
        "market_fees": 0.0,
        "sale_count": 0,
        "quantity": 0.0,
        "by_source": {},
        "by_item": {},
    }


def _add_sale(
    bucket: dict[str, Any], *, source: str, item_id: str, quantity: float,
    seller_cash: float, buyer_cash: float, fees: float = 0.0, count: int = 1,
) -> None:
    bucket["seller_cash_received"] += seller_cash
    bucket["buyer_cash_paid"] += buyer_cash
    bucket["market_fees"] += fees
    bucket["sale_count"] += count
    bucket["quantity"] += quantity
    for collection, key in (("by_source", source), ("by_item", item_id)):
        detail = bucket[collection].setdefault(key, _empty_bucket())
        detail["seller_cash_received"] += seller_cash
        detail["buyer_cash_paid"] += buyer_cash
        detail["market_fees"] += fees
        detail["sale_count"] += count
        detail["quantity"] += quantity


def _round_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    return {
        "seller_cash_received": round(bucket["seller_cash_received"], 2),
        "buyer_cash_paid": round(bucket["buyer_cash_paid"], 2),
        "market_fees": round(bucket["market_fees"], 2),
        "sale_count": int(bucket["sale_count"]),
        "quantity": round(bucket["quantity"], 6),
        "by_source": {key: _round_bucket(value) for key, value in sorted(bucket["by_source"].items())},
        "by_item": {key: _round_bucket(value) for key, value in sorted(bucket["by_item"].items())},
    }


def _finite_positive(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) and result > 0 else 0.0


class LiquidityService:
    """Build or persist the sector receipt totals for ``[now - 24h, now)``.

    City orders retain event-time industry, so they are attributed to a sector.
    Market trades and supply deliveries do not retain the seller's industry and
    are kept under ``unassigned`` instead of using a mutable current company
    specialization. NPC sell telemetry is timestamped in UTC; the other sale
    ledgers use local game time.
    """

    @staticmethod
    async def aggregate_24h(
        session: AsyncSession, *, now: datetime | None = None,
    ) -> dict[str, Any]:
        window_end = normalize_dt(now or get_game_now())
        assert window_end is not None
        window_start = window_end - timedelta(hours=24)
        tz = get_game_tz()
        utc_end = window_end.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
        utc_start = utc_end - timedelta(hours=24)

        sectors = {
            industry_id: {
                "industry_id": industry_id,
                "industry_name": metadata["name"],
                **_empty_bucket(),
            }
            for industry_id, metadata in INDUSTRIES.items()
        }
        unassigned = _empty_bucket()

        market_rows = (await session.execute(
            select(
                NatMarketTrade.item_id,
                func.sum(NatMarketTrade.total_amount),
                func.sum(NatMarketTrade.fee_amount),
                func.sum(NatMarketTrade.quantity),
                func.count(NatMarketTrade.id),
            ).where(
                NatMarketTrade.executed_at >= window_start,
                NatMarketTrade.executed_at < window_end,
                NatMarketTrade.sell_order_id.is_not(None),
                NatMarketTrade.total_amount > 0,
                NatMarketTrade.quantity > 0,
                NatMarketTrade.fee_amount >= 0,
                NatMarketTrade.fee_amount <= NatMarketTrade.total_amount,
            ).group_by(NatMarketTrade.item_id)
        )).all()
        for item_id, gross, fee, quantity, count in market_rows:
            gross_cash = _finite_positive(gross)
            fee_cash = max(0.0, float(fee or 0.0))
            qty = _finite_positive(quantity)
            if not item_id or not gross_cash or not qty or fee_cash > gross_cash:
                continue
            _add_sale(
                unassigned, source="market_trades", item_id=item_id, quantity=qty,
                buyer_cash=gross_cash, seller_cash=gross_cash - fee_cash,
                fees=fee_cash, count=int(count or 0),
            )

        supply_rows = (await session.execute(
            select(
                NatSupplyDealSettlement.item_id,
                func.sum(NatSupplyDealSettlement.cash_amount),
                func.sum(NatSupplyDealSettlement.quantity),
                func.count(NatSupplyDealSettlement.id),
            ).where(
                NatSupplyDealSettlement.settlement_type == "DELIVERY",
                NatSupplyDealSettlement.created_at >= window_start,
                NatSupplyDealSettlement.created_at < window_end,
                NatSupplyDealSettlement.item_id.is_not(None),
                NatSupplyDealSettlement.cash_amount > 0,
                NatSupplyDealSettlement.quantity > 0,
            ).group_by(NatSupplyDealSettlement.item_id)
        )).all()
        for item_id, cash, quantity, count in supply_rows:
            amount = _finite_positive(cash)
            qty = _finite_positive(quantity)
            if not item_id or not amount or not qty:
                continue
            _add_sale(
                unassigned, source="supply_deals", item_id=item_id,
                quantity=qty, buyer_cash=amount, seller_cash=amount,
                count=int(count or 0),
            )

        city_rows = (await session.execute(
            select(
                NatCityOrderDelivery.seller_industry,
                NatCityOrderDelivery.item_id,
                func.sum(NatCityOrderDelivery.cash_amount),
                func.sum(NatCityOrderDelivery.quantity),
                func.count(NatCityOrderDelivery.id),
            ).where(
                NatCityOrderDelivery.created_at >= window_start,
                NatCityOrderDelivery.created_at < window_end,
                NatCityOrderDelivery.cash_amount > 0,
                NatCityOrderDelivery.quantity > 0,
            ).group_by(NatCityOrderDelivery.seller_industry, NatCityOrderDelivery.item_id)
        )).all()
        for industry_id, item_id, cash, quantity, count in city_rows:
            amount = _finite_positive(cash)
            qty = _finite_positive(quantity)
            if not item_id or not amount or not qty:
                continue
            bucket = sectors.get(industry_id, unassigned)
            _add_sale(
                bucket, source="city_orders", item_id=item_id, quantity=qty,
                buyer_cash=amount, seller_cash=amount, count=int(count or 0),
            )

        npc_rows = (await session.execute(
            select(
                NatEconomyEvent.item_id,
                func.sum(NatEconomyEvent.cash_amount),
                func.sum(NatEconomyEvent.quantity),
                func.count(NatEconomyEvent.id),
            ).where(
                NatEconomyEvent.flow == "SOURCE",
                NatEconomyEvent.category == "npc_sell",
                NatEconomyEvent.created_at >= utc_start,
                NatEconomyEvent.created_at < utc_end,
                NatEconomyEvent.item_id.is_not(None),
                NatEconomyEvent.cash_amount > 0,
                NatEconomyEvent.quantity > 0,
            ).group_by(NatEconomyEvent.item_id)
        )).all()
        for item_id, cash, quantity, count in npc_rows:
            amount = _finite_positive(cash)
            qty = _finite_positive(quantity)
            if not item_id or not amount or not qty:
                continue
            _add_sale(
                unassigned, source="npc_reserve_sales", item_id=item_id,
                quantity=qty, buyer_cash=amount, seller_cash=amount,
                count=int(count or 0),
            )

        rounded_sectors = {key: _round_bucket(value) for key, value in sorted(sectors.items())}
        rounded_unassigned = _round_bucket(unassigned)
        buckets = [*rounded_sectors.values(), rounded_unassigned]
        total_seller = round(sum(row["seller_cash_received"] for row in buckets), 2)
        total_buyer = round(sum(row["buyer_cash_paid"] for row in buckets), 2)
        total_fees = round(sum(row["market_fees"] for row in buckets), 2)
        sale_count = sum(row["sale_count"] for row in buckets)

        return {
            "window_start": window_start,
            "window_end": window_end,
            "total_seller_cash_received": total_seller,
            "total_buyer_cash_paid": total_buyer,
            "total_market_fees": total_fees,
            "sale_count": sale_count,
            "sectors": rounded_sectors,
            "unassigned": rounded_unassigned,
            "coverage": {
                "included_sources": {
                    "market_trades": "matched NatMarketTrade.total_amount minus fee_amount; seller industry is not snapshotted",
                    "supply_deals": "NatSupplyDealSettlement.cash_amount where settlement_type=DELIVERY; seller industry is not snapshotted",
                    "city_orders": "NatCityOrderDelivery.cash_amount grouped by event-time seller_industry",
                    "npc_reserve_sales": "NatEconomyEvent SOURCE/npc_sell; UTC event timestamp",
                },
                "excluded_sources": [
                    "NatNpcDailyVolume: date-only aggregates cannot be sliced to an exact rolling 24-hour window",
                    "NatCityOrder.paid_cash: cumulative mirror of NatCityOrderDelivery.cash_amount",
                    "company profit and business income ledgers: accounting mirrors of sale cash already counted above",
                    "NatMarketTrade rows with sell_order_id=NULL: forced-bankruptcy liquidation proceeds go to the state treasury",
                    "open or reserved NatMarketOrder cash: no completed sale has occurred",
                ],
                "time_window": "half-open [window_start, window_end); game-local timestamps except UTC NatEconomyEvent",
            },
        }

    @staticmethod
    async def record_snapshot(
        session: AsyncSession, *, now: datetime | None = None,
    ) -> NatLiquiditySnapshot:
        report = await LiquidityService.aggregate_24h(session, now=now)
        snapshot = (await session.execute(
            select(NatLiquiditySnapshot)
            .where(NatLiquiditySnapshot.window_end == report["window_end"])
            .with_for_update()
        )).scalar_one_or_none()
        values = {
            "window_start": report["window_start"],
            "window_end": report["window_end"],
            "total_seller_cash_received": report["total_seller_cash_received"],
            "total_buyer_cash_paid": report["total_buyer_cash_paid"],
            "total_market_fees": report["total_market_fees"],
            "sale_count": report["sale_count"],
            "sectors_json": report["sectors"],
            "unassigned_json": report["unassigned"],
            "coverage_json": report["coverage"],
        }
        if snapshot is None:
            snapshot = NatLiquiditySnapshot(**values)
            session.add(snapshot)
        else:
            for key, value in values.items():
                setattr(snapshot, key, value)
        await session.flush()
        return snapshot


__all__ = ["LiquidityService"]
