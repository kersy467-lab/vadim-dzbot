"""Supply, fleet, employee and project rows owned by a tycoon business."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models import Base


class NatBusinessSupplyPolicy(Base):
    __tablename__ = "nat_business_supply_policies"
    __table_args__ = (UniqueConstraint("business_id", "item_id", name="uq_nat_business_supply_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False)
    min_hours_stock: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    target_hours_stock: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    allow_state_reserve: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    business = relationship("NatBusiness", back_populates="supply_policies")


class NatBusinessVehicle(Base):
    __tablename__ = "nat_business_vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vehicle_type: Mapped[str] = mapped_column(String(64), nullable=False)
    vehicle_tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    condition: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    max_condition: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    income_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    wear_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    auto_maintenance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    business = relationship("NatBusiness", back_populates="vehicles")


class NatBusinessEmployee(Base):
    __tablename__ = "nat_business_employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    skill: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    salary_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    business = relationship("NatBusiness", back_populates="employees")


class NatBusinessProject(Base):
    __tablename__ = "nat_business_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ready_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reward_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    business = relationship("NatBusiness", back_populates="projects")


__all__ = [
    "NatBusinessSupplyPolicy",
    "NatBusinessVehicle",
    "NatBusinessEmployee",
    "NatBusinessProject",
]
