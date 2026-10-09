"""Persisted sandbox company for the admin-only next-game preview."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatNextGameCompany(Base):
    __tablename__ = "nat_next_game_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sector_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    branch_path: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    cash: Mapped[float] = mapped_column(Float, default=10_000.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


__all__ = ["NatNextGameCompany"]
