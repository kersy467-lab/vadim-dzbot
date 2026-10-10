"""Reserve-bank bond series, ownership lots and secondary-market escrow."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base
from backend.natbirzha.models.next_game import _utcnow


class NatNextGameBondSeries(Base):
    __tablename__ = "nat_next_game_bond_series"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    face_price: Mapped[float] = mapped_column(Float, nullable=False)
    daily_rate: Mapped[float] = mapped_column(Float, nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)


class NatNextGameBondHolding(Base):
    __tablename__ = "nat_next_game_bond_holdings"
    __table_args__ = (
        CheckConstraint("units >= 0", name="ck_next_bond_units"),
        CheckConstraint("status IN ('ACTIVE','MATURED','TRANSFERRED','FORFEITED')", name="ck_next_bond_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_next_game_companies.id", ondelete="RESTRICT"), index=True)
    series_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_next_game_bond_series.id"), index=True)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    matures_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    last_coupon_at: Mapped[datetime] = mapped_column(DateTime)
    accrual_started_at: Mapped[datetime] = mapped_column(DateTime)
    accrual_paid: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    coupon_remaining: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    coupon_paid: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)


class NatNextGameBondListing(Base):
    __tablename__ = "nat_next_game_bond_listings"
    __table_args__ = (
        CheckConstraint("units >= 0", name="ck_next_bond_listing_units"),
        CheckConstraint("unit_price > 0", name="ck_next_bond_listing_price"),
        CheckConstraint("status IN ('OPEN','FILLED','CANCELLED','MATURED','FORFEITED')", name="ck_next_bond_listing_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holding_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_next_game_bond_holdings.id", ondelete="RESTRICT"), index=True)
    seller_company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_next_game_companies.id", ondelete="RESTRICT"), index=True)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


__all__ = ["NatNextGameBondSeries", "NatNextGameBondHolding", "NatNextGameBondListing"]
