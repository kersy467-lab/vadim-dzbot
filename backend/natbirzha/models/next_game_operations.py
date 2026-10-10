"""Isolated paid capacity, workforce and fleet; no legacy asset foreign keys."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base


class NatNextGameOperations(Base):
    __tablename__ = "nat_next_game_operations"
    __table_args__ = (CheckConstraint("land_level BETWEEN 0 AND 10 AND warehouse_level BETWEEN 0 AND 10"),)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), primary_key=True)
    land_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warehouse_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class NatNextGameFactoryOperations(Base):
    __tablename__ = "nat_next_game_factory_operations"
    __table_args__ = (CheckConstraint("automation_level BETWEEN 0 AND 5"),)
    facility_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_facilities.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    license_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameEmployee(Base):
    __tablename__ = "nat_next_game_employees"
    __table_args__ = (UniqueConstraint("facility_id", "role"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(48), nullable=False)


class NatNextGameVehicle(Base):
    __tablename__ = "nat_next_game_vehicles"
    __table_args__ = (CheckConstraint("condition BETWEEN 0 AND 100"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(48), nullable=False)
    condition: Mapped[float] = mapped_column(Float, default=100, nullable=False)
