"""Isolated NATBIRZHA 2.0 persistence; no legacy economic foreign keys."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON,
    String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NatNextGameCompany(Base):
    __tablename__ = "nat_next_game_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sector_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    branch_path: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    cash: Mapped[float] = mapped_column(Float, default=10_000.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class NatNextGameInventory(Base):
    __tablename__ = "nat_next_game_inventory"
    __table_args__ = (
        UniqueConstraint("company_id", "item_id", name="uq_next_game_inventory_item"),
        CheckConstraint("quantity >= 0", name="ck_next_game_inventory_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class NatNextGameFacility(Base):
    __tablename__ = "nat_next_game_facilities"
    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", name="uq_next_game_facility_branch"),
        CheckConstraint("level >= 1", name="ck_next_game_facility_level_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    next_cycle_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class NatNextGameTreasury(Base):
    __tablename__ = "nat_next_game_treasury"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cash: Mapped[float] = mapped_column(Float, default=100_000_000.0, nullable=False)
    inventory_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class NatNextGameLedger(Base):
    __tablename__ = "nat_next_game_ledger"
    __table_args__ = (
        CheckConstraint(
            "ABS(cash_company_delta + cash_treasury_delta) < 0.01",
            name="ck_next_game_cash_double_entry",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    cash_company_delta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cash_treasury_delta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity_company_delta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quantity_treasury_delta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)


class NatNextGameLoan(Base):
    __tablename__ = "nat_next_game_loans"
    __table_args__ = (
        CheckConstraint("principal > 0", name="ck_next_game_loan_principal_positive"),
        CheckConstraint("status IN ('ACTIVE', 'PAID')", name="ck_next_game_loan_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameDeposit(Base):
    __tablename__ = "nat_next_game_deposits"
    __table_args__ = (
        CheckConstraint("principal > 0", name="ck_next_game_deposit_principal_positive"),
        CheckConstraint("maturity_amount >= principal", name="ck_next_game_deposit_maturity_range"),
        CheckConstraint("term_days BETWEEN 1 AND 30", name="ck_next_game_deposit_term_range"),
        CheckConstraint("daily_rate >= 0", name="ck_next_game_deposit_rate_nonnegative"),
        CheckConstraint("status IN ('ACTIVE', 'WITHDRAWN')", name="ck_next_game_deposit_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    maturity_amount: Mapped[float] = mapped_column(Float, nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_rate: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    matures_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameMarketOrder(Base):
    """Reserved limit order in the isolated NATBIRZHA 2.0 company market."""

    __tablename__ = "nat_next_game_market_orders"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_next_game_order_side"),
        CheckConstraint("status IN ('OPEN', 'FILLED', 'CANCELLED')", name="ck_next_game_order_status"),
        CheckConstraint("limit_price > 0", name="ck_next_game_order_price_positive"),
        CheckConstraint("quantity > 0", name="ck_next_game_order_quantity_positive"),
        CheckConstraint(
            "remaining_quantity >= 0 AND remaining_quantity <= quantity",
            name="ck_next_game_order_remaining_range",
        ),
        CheckConstraint("reserved_cash >= 0", name="ck_next_game_order_cash_nonnegative"),
        Index("ix_next_game_order_book", "item_id", "side", "status", "limit_price", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    limit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    reserved_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class NatNextGameMarketTrade(Base):
    """Append-only execution audit for company-to-company 2.0 trades."""

    __tablename__ = "nat_next_game_market_trades"
    __table_args__ = (
        CheckConstraint("buyer_company_id <> seller_company_id", name="ck_next_game_trade_distinct_companies"),
        CheckConstraint("quantity > 0", name="ck_next_game_trade_quantity_positive"),
        CheckConstraint("price > 0", name="ck_next_game_trade_price_positive"),
        Index("ix_next_game_trade_item_time", "item_id", "executed_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buy_order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sell_order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    buyer_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seller_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)


__all__ = [
    "NatNextGameCompany", "NatNextGameFacility", "NatNextGameInventory",
    "NatNextGameLedger", "NatNextGameLoan", "NatNextGameDeposit", "NatNextGameMarketOrder",
    "NatNextGameMarketTrade", "NatNextGameTreasury",
]
