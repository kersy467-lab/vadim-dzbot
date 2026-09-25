"""Core persistent state for NATBIRZHA 2.0 idle businesses."""

from datetime import date, datetime
from typing import Any, List, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models import Base


BUSINESS_STATUSES = frozenset({
    "ACTIVE",
    "UPGRADING",
    "PAUSED_MANUAL",
    "PAUSED_SUPPLY",
    "PAUSED_MAINTENANCE",
    "PAUSED_STORAGE",
    "BANKRUPT",
    "MERGING",
})


class NatBusiness(Base):
    """One company-owned idle enterprise; formulas remain in the business catalog."""

    __tablename__ = "nat_businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    custom_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    specialization: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    stage: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False, index=True)
    capital_invested: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    base_income_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    base_maintenance_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_settled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    upgrade_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    upgrade_ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    upgrade_target_stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    health: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    efficiency: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    slot_weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    supply_policies: Mapped[List["NatBusinessSupplyPolicy"]] = relationship(
        "NatBusinessSupplyPolicy", back_populates="business", cascade="all, delete-orphan"
    )
    vehicles: Mapped[List["NatBusinessVehicle"]] = relationship(
        "NatBusinessVehicle", back_populates="business", cascade="all, delete-orphan"
    )
    employees: Mapped[List["NatBusinessEmployee"]] = relationship(
        "NatBusinessEmployee", back_populates="business", cascade="all, delete-orphan"
    )
    projects: Mapped[List["NatBusinessProject"]] = relationship(
        "NatBusinessProject", back_populates="business", cascade="all, delete-orphan"
    )


class NatBusinessIncomeDaily(Base):
    """Daily aggregates used by analytics, NAV, IPO and dividends."""

    __tablename__ = "nat_business_income_daily"
    __table_args__ = (UniqueConstraint("business_id", "date", name="uq_nat_business_income_daily"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_income: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    maintenance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    salary: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resource_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    net_profit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class NatBusinessIncomePeriod(Base):
    """12-hour period operating profit aggregates used for mandatory taxation."""

    __tablename__ = "nat_business_income_periods"
    __table_args__ = (
        UniqueConstraint("business_id", "period_start", name="uq_nat_business_income_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gross_income: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    maintenance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    salary: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resource_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    net_profit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class NatCompanyEconomyState(Base):
    """Non-authoritative cache for fast empire summaries."""

    __tablename__ = "nat_company_economy_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    cached_income_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cached_expenses_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cached_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


__all__ = [
    "BUSINESS_STATUSES",
    "NatBusiness",
    "NatBusinessIncomeDaily",
    "NatBusinessIncomePeriod",
    "NatCompanyEconomyState",
]
