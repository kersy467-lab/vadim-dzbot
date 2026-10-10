"""Isolated daily tax accounting, reserve procurement and sector events."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base


class NatNextGameTaxAccount(Base):
    __tablename__ = "nat_next_game_tax_accounts"
    __table_args__ = (CheckConstraint("loss_carry >= 0", name="ck_next_civic_carry"),)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), primary_key=True)
    epoch_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    assessed_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    loss_carry: Mapped[float] = mapped_column(Float, default=0, nullable=False)


class NatNextGameTaxAssessment(Base):
    __tablename__ = "nat_next_game_tax_assessments"
    __table_args__ = (
        UniqueConstraint("company_id", "period_start", "period_end", name="uq_next_civic_tax_period"),
        CheckConstraint("amount >= 0 AND taxable_profit >= 0", name="ck_next_civic_tax_nonnegative"),
        CheckConstraint("status IN ('DUE', 'PAID', 'FORGIVEN')", name="ck_next_civic_tax_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    operating_profit: Mapped[float] = mapped_column(Float)
    taxable_profit: Mapped[float] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="DUE")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameCityOrder(Base):
    __tablename__ = "nat_next_game_city_orders"
    __table_args__ = (
        UniqueConstraint("rotation_at", "item_id", name="uq_next_civic_order_rotation"),
        CheckConstraint("unit_price > 0 AND quantity > 0", name="ck_next_civic_order_positive"),
        CheckConstraint("remaining_quantity >= 0 AND remaining_quantity <= quantity", name="ck_next_civic_order_remaining"),
        CheckConstraint("status IN ('OPEN', 'FILLED', 'EXPIRED')", name="ck_next_civic_order_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64))
    unit_price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    remaining_quantity: Mapped[float] = mapped_column(Float)
    rotation_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(12), default="OPEN")


class NatNextGameEconomicEvent(Base):
    __tablename__ = "nat_next_game_economic_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector_id: Mapped[str] = mapped_column(String(48), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    creator_tg_id: Mapped[int] = mapped_column(Integer)
