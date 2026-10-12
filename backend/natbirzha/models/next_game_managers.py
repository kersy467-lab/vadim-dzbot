"""Deterministic company manager rewards and their single-factory assignments."""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NatNextGameManager(Base):
    __tablename__ = "nat_next_game_managers"
    __table_args__ = (
        UniqueConstraint("company_id", "reward_level", name="uq_next_manager_reward"),
        UniqueConstraint("facility_id", name="uq_next_manager_facility"),
        CheckConstraint("discount_pct IN (2, 4, 6, 8)", name="ck_next_manager_discount"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    reward_level: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), nullable=False)
    # Legacy schema field retained because deployed databases constrain this
    # column to 2/4/6/8. It is storage-only: manager strength comes from rarity.
    discount_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    # Milestone staff are guaranteed; case staff are collectible hires.
    # reward_level remains the per-company unique key for both sources, while
    # level is the employee's visible level and may repeat for case drops.
    source: Mapped[str] = mapped_column(
        String(16), default="milestone", server_default="milestone", nullable=False,
    )
    level: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    facility_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_next_game_facilities.id", ondelete="SET NULL"),
        nullable=True,
    )
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


__all__ = ["NatNextGameManager"]
