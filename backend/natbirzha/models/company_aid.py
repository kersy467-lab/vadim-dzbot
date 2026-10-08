"""Requests and audit records for voluntary company-to-company aid."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatCompanyAidRequest(Base):
    __tablename__ = "nat_company_aid_requests"
    __table_args__ = (
        CheckConstraint("kind IN ('cash', 'item')", name="ck_nat_aid_request_kind"),
        CheckConstraint("status IN ('OPEN', 'FULFILLED', 'CANCELLED')", name="ck_nat_aid_request_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    amount_cash: Mapped[float | None] = mapped_column(Float, nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    item_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    fulfilled_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fulfilled_value_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NatCompanyAidTransfer(Base):
    __tablename__ = "nat_company_aid_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_company_aid_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cash_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    item_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    item_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    aid_value_cash: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


__all__ = ["NatCompanyAidRequest", "NatCompanyAidTransfer"]
