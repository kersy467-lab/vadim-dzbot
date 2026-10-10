"""Bilateral company financing contracts for NATBIRZHA 2.0."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NatNextGameFinanceContract(Base):
    __tablename__ = "nat_next_game_finance_contracts"
    __table_args__ = (
        UniqueConstraint("lender_company_id", "offer_key", name="uq_next_game_finance_offer_key"),
        CheckConstraint("lender_company_id <> borrower_company_id", name="ck_next_game_finance_distinct"),
        CheckConstraint("principal BETWEEN 1000 AND 100000", name="ck_next_game_finance_principal"),
        CheckConstraint("daily_rate_bps BETWEEN 0 AND 100", name="ck_next_game_finance_rate"),
        CheckConstraint("term_days BETWEEN 1 AND 30", name="ck_next_game_finance_term"),
        CheckConstraint("maturity_amount >= principal", name="ck_next_game_finance_maturity"),
        CheckConstraint("status IN ('OPEN', 'ACTIVE', 'PAID', 'CANCELLED')", name="ck_next_game_finance_status"),
        Index("ix_next_game_finance_borrower_status", "borrower_company_id", "status"),
        Index("ix_next_game_finance_lender_time", "lender_company_id", "offered_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lender_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    borrower_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    daily_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    maturity_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    offer_key: Mapped[str] = mapped_column(String(128), nullable=False)
    accept_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cancel_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repayment_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    offered_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repaid_amount: Mapped[float | None] = mapped_column(Float, nullable=True)


__all__ = ["NatNextGameFinanceContract"]
