"""Small write-only telemetry layer used to tune the live game economy."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.economy_metrics import NatEconomyEvent


class EconomyMetricsService:
    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        company_id: Optional[int],
        flow: str,
        category: str,
        cash_amount: float = 0.0,
        item_id: Optional[str] = None,
        quantity: float = 0.0,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        session.add(NatEconomyEvent(
            company_id=company_id,
            flow=flow.upper(),
            category=category,
            cash_amount=round(abs(float(cash_amount or 0.0)), 2),
            item_id=item_id,
            quantity=round(abs(float(quantity or 0.0)), 4),
            context_json=json.dumps(context or {}, ensure_ascii=False, separators=(",", ":")),
        ))

    @staticmethod
    async def summary(session: AsyncSession, *, days: int = 7) -> dict[str, Any]:
        days = min(max(int(days), 1), 90)
        since = datetime.utcnow() - timedelta(days=days)
        rows = list((await session.execute(
            select(NatEconomyEvent).where(NatEconomyEvent.created_at >= since)
        )).scalars().all())
        cash_by_flow: dict[str, float] = defaultdict(float)
        categories: dict[str, dict[str, float]] = defaultdict(lambda: {"cash": 0.0, "quantity": 0.0, "events": 0})
        for row in rows:
            cash_by_flow[row.flow] += float(row.cash_amount or 0.0)
            bucket = categories[row.category]
            bucket["cash"] += float(row.cash_amount or 0.0)
            bucket["quantity"] += float(row.quantity or 0.0)
            bucket["events"] += 1
        sources = cash_by_flow.get("SOURCE", 0.0)
        sinks = cash_by_flow.get("SINK", 0.0)
        return {
            "window_days": days,
            "events": len(rows),
            "cash_sources": round(sources, 2),
            "cash_sinks": round(sinks, 2),
            "net_cash_faucet": round(sources - sinks, 2),
            "categories": {
                key: {
                    "cash": round(value["cash"], 2),
                    "quantity": round(value["quantity"], 4),
                    "events": int(value["events"]),
                }
                for key, value in sorted(categories.items())
            },
        }


__all__ = ["EconomyMetricsService"]
