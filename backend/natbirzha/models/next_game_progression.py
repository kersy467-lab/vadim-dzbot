"""Source-consuming factory mergers in the isolated 2.0 economy."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base
from backend.natbirzha.models.next_game import _utcnow


class NatNextGameMerger(Base):
    __tablename__ = "nat_next_game_mergers"
    __table_args__ = (CheckConstraint("status IN ('ACTIVE', 'DISSOLVED', 'RESET')", name="ck_next_merger_status"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sources_json: Mapped[list] = mapped_column(JSON, nullable=False)
    recipe_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    dissolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
