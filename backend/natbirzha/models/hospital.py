"""Persistent hospital and repair-depot queues for military units."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatHospitalWard(Base):
    __tablename__ = "nat_hospital_wards"
    __table_args__ = (
        UniqueConstraint("company_id", "unit_type", name="uq_nat_hospital_company_unit"),
        CheckConstraint("wounded_count >= 0", name="ck_nat_hospital_wounded_nonnegative"),
        CheckConstraint("healing_count >= 0", name="ck_nat_hospital_healing_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    wounded_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    healing_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    healing_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    healing_ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )