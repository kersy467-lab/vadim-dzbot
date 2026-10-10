"""Treasury advances collateralized by isolated reserved SELL orders."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base
from backend.natbirzha.models.next_game import _utcnow


class NatNextGameMarketAdvance(Base):
    __tablename__ = "nat_next_game_market_advances"
    __table_args__ = (
        CheckConstraint("advance_paid > 0 AND advance_paid <= 30000", name="ck_next_advance_paid"),
        CheckConstraint("outstanding_amount >= 0 AND outstanding_amount <= advance_paid", name="ck_next_advance_outstanding"),
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_market_orders.id", ondelete="RESTRICT"), primary_key=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="RESTRICT"), index=True, nullable=False,
    )
    advance_paid: Mapped[float] = mapped_column(Float, nullable=False)
    outstanding_amount: Mapped[float] = mapped_column(Float, nullable=False)
    reference_price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


__all__ = ["NatNextGameMarketAdvance"]
