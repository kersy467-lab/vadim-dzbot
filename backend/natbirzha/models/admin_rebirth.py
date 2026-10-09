"""Audited, delayed creator rebirth operations."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatAdminRebirthSchedule(Base):
    __tablename__ = "nat_admin_rebirth_schedules"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AWAITING_WARNING', 'PENDING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_nat_admin_rebirth_schedule_status",
        ),
        Index("ix_nat_admin_rebirth_due", "status", "execute_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    company_ids_json: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    expected_counts_json: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    created_by_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="AWAITING_WARNING", nullable=False)
    warning_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execute_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


__all__ = ["NatAdminRebirthSchedule"]
