"""Persistent ownership and source-business snapshot for active hybrids."""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatHybridMerger(Base):
    """A server-owned hybrid recipe formed from two existing businesses.

    Original business capital remains on the source ``NatBusiness`` rows. Only
    the extra hybrid investment is recorded here and eligible for a sale refund.
    """

    __tablename__ = "nat_hybrid_mergers"
    __table_args__ = (
        CheckConstraint(
            "source_business_a_id <> source_business_b_id",
            name="ck_nat_hybrid_distinct_sources",
        ),
        CheckConstraint(
            "additional_capital_invested >= 0",
            name="ck_nat_hybrid_nonnegative_capital",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'SOLD')",
            name="ck_nat_hybrid_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nat_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipe_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    specialization: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_business_a_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nat_businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_business_b_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nat_businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    hybrid_business_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("nat_businesses.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    source_a_stage: Mapped[int] = mapped_column(Integer, nullable=False)
    source_b_stage: Mapped[int] = mapped_column(Integer, nullable=False)
    source_a_slot_weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_b_slot_weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_a_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_b_status: Mapped[str] = mapped_column(String(32), nullable=False)
    additional_capital_invested: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


__all__ = ["NatHybridMerger"]
