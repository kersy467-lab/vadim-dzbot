"""Treasury-backed state credit obligations."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatStateCreditLoan(Base):
    __tablename__ = "nat_state_credit_loans"
    __table_args__ = (
        Index("ix_nat_state_credit_loans_company_status", "company_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("nat_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    total_due: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_debt: Mapped[float] = mapped_column(Float, nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", nullable=False, index=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


__all__ = ["NatStateCreditLoan"]
