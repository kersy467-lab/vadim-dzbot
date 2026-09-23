"""Independent government-share issues, player positions and dividend ledger."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatStateShare(Base):
    __tablename__ = "nat_state_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    total_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_price: Mapped[float] = mapped_column(Float, nullable=False)
    projected_annual_profit: Mapped[float] = mapped_column(Float, nullable=False)
    dividend_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatStateShareHolding(Base):
    __tablename__ = "nat_state_share_holdings"
    __table_args__ = (
        UniqueConstraint("share_id", "company_id", name="uq_nat_state_share_holding_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_state_shares.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invested_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dividends_earned: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatStateShareOperation(Base):
    """Durable operation keys make direct service retries safe as well as HTTP retries."""

    __tablename__ = "nat_state_share_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(24), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatStateShareDailySettlement(Base):
    __tablename__ = "nat_state_share_daily_settlements"
    __table_args__ = (UniqueConstraint("settlement_date", name="uq_nat_state_share_settlement_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_due: Mapped[float] = mapped_column(Float, nullable=False)
    total_paid: Mapped[float] = mapped_column(Float, nullable=False)
    proration_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    treasury_cash_before: Mapped[float] = mapped_column(Float, nullable=False)
    treasury_cash_after: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatStateShareDividendPayment(Base):
    __tablename__ = "nat_state_share_dividend_payments"
    __table_args__ = (
        UniqueConstraint("share_id", "company_id", "settlement_date", name="uq_nat_state_share_payment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    settlement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_state_share_daily_settlements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    share_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_state_shares.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_due: Mapped[float] = mapped_column(Float, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Float, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


__all__ = [
    "NatStateShare",
    "NatStateShareHolding",
    "NatStateShareOperation",
    "NatStateShareDailySettlement",
    "NatStateShareDividendPayment",
]
