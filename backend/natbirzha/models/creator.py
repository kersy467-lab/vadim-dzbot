from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, BigInteger, String, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base

class NatStateTreasury(Base):
    __tablename__ = "nat_state_treasury"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cash: Mapped[float] = mapped_column(Float, default=10000000.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NatCreatorAuditLog(Base):
    __tablename__ = "nat_creator_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class NatMarketRestriction(Base):
    __tablename__ = "nat_market_restrictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=True, index=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    min_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatMarketWarning(Base):
    __tablename__ = "nat_market_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatStateBond(Base):
    __tablename__ = "nat_state_bonds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    total_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    face_value: Mapped[float] = mapped_column(Float, nullable=False)
    coupon_rate: Mapped[float] = mapped_column(Float, nullable=False)
    maturity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # Coupon cadence is daily by default; explicit legacy intervals remain supported.
    coupon_interval_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OFFERING", nullable=False, index=True)
    next_coupon_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    maturity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatStateBondHolding(Base):
    __tablename__ = "nat_state_bond_holdings"
    __table_args__ = (
        UniqueConstraint("bond_id", "company_id", name="uq_nat_bond_holding_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bond_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_state_bonds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invested_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NatBondSettlement(Base):
    __tablename__ = "nat_bond_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    bond_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_state_bonds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    settlement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    period_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entitled_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_rub: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatBondListing(Base):
    __tablename__ = "nat_bond_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    bond_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_state_bonds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seller_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True)
    filled_operation_key: Mapped[Optional[str]] = mapped_column(String(160), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
