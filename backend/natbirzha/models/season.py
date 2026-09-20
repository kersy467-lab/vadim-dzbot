"""Auditable idempotency record for an explicitly authorized season reset."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatSeasonResetOperation(Base):
    __tablename__ = "nat_season_reset_operations"
    __table_args__ = (UniqueConstraint("operation_id", name="uq_nat_season_reset_operation_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_tg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    backup_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    affected_companies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


__all__ = ["NatSeasonResetOperation"]
