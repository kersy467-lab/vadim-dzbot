"""Append-only economy telemetry for balancing sources, sinks and item flows."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatEconomyEvent(Base):
    __tablename__ = "nat_economy_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    flow: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    cash_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    item_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


__all__ = ["NatEconomyEvent"]
