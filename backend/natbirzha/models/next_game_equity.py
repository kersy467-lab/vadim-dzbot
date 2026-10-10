"""Isolated 2.0 company shares, order book and dividend audit."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Index, Integer,
    String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NatNextGameShareIssue(Base):
    __tablename__ = "nat_next_game_share_issues"
    __table_args__ = (
        CheckConstraint("total_shares > 0", name="ck_next_game_ipo_total_positive"),
        CheckConstraint("float_shares BETWEEN 1 AND total_shares", name="ck_next_game_ipo_float_range"),
        CheckConstraint("initial_price > 0 AND last_price > 0", name="ck_next_game_ipo_price_positive"),
        CheckConstraint("status IN ('ACTIVE', 'CLOSED')", name="ck_next_game_ipo_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    total_shares: Mapped[int] = mapped_column(Integer, nullable=False)
    float_shares: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_price: Mapped[float] = mapped_column(Float, nullable=False)
    last_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)
    listed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class NatNextGameShareHolding(Base):
    __tablename__ = "nat_next_game_share_holdings"
    __table_args__ = (
        UniqueConstraint("issue_id", "company_id", name="uq_next_game_share_holder"),
        CheckConstraint("shares >= 0", name="ck_next_game_share_holding_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_share_issues.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class NatNextGameShareOrder(Base):
    __tablename__ = "nat_next_game_share_orders"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_next_game_share_order_side"),
        CheckConstraint("status IN ('OPEN', 'FILLED', 'CANCELLED')", name="ck_next_game_share_order_status"),
        CheckConstraint("limit_price > 0", name="ck_next_game_share_order_price_positive"),
        CheckConstraint("quantity > 0", name="ck_next_game_share_order_quantity_positive"),
        CheckConstraint("remaining_shares >= 0 AND remaining_shares <= quantity", name="ck_next_game_share_order_remaining"),
        CheckConstraint("reserved_cash >= 0", name="ck_next_game_share_order_cash_nonnegative"),
        Index("ix_next_game_share_book", "issue_id", "side", "status", "limit_price", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_share_issues.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    limit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_shares: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class NatNextGameShareTrade(Base):
    __tablename__ = "nat_next_game_share_trades"
    __table_args__ = (
        CheckConstraint("buyer_company_id <> seller_company_id", name="ck_next_game_share_trade_distinct"),
        CheckConstraint("shares > 0 AND price > 0", name="ck_next_game_share_trade_positive"),
        Index("ix_next_game_share_trade_time", "issue_id", "executed_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_share_issues.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    buy_order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sell_order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    buyer_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    seller_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)


class NatNextGameDividend(Base):
    __tablename__ = "nat_next_game_dividends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_share_issues.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    issuer_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    per_share: Mapped[float] = mapped_column(Float, nullable=False)
    total_paid: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)


class NatNextGameDividendPayment(Base):
    __tablename__ = "nat_next_game_dividend_payments"
    __table_args__ = (
        UniqueConstraint("dividend_id", "company_id", name="uq_next_game_dividend_payment"),
        CheckConstraint("shares > 0 AND amount >= 0", name="ck_next_game_dividend_payment_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dividend_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_dividends.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)


__all__ = [
    "NatNextGameShareIssue", "NatNextGameShareHolding", "NatNextGameShareOrder",
    "NatNextGameShareTrade", "NatNextGameDividend", "NatNextGameDividendPayment",
]
