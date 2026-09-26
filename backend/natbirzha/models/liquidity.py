"""Persisted snapshots of exact paid sales over a rolling 24-hour window."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatLiquiditySnapshot(Base):
    __tablename__ = "nat_liquidity_snapshots"
    __table_args__ = (Index("uq_nat_liquidity_snapshot_window_end", "window_end", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_seller_cash_received: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_buyer_cash_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_market_fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sale_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sectors_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    unassigned_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    coverage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )


__all__ = ["NatLiquiditySnapshot"]
