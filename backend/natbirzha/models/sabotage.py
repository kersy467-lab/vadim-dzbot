"""Database model for active and historical Natbirzha economic sabotages."""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Integer, BigInteger, String, Boolean, DateTime, JSON
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base


class NatActiveSabotage(Base):
    __tablename__ = "nat_active_sabotages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sabotage_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    started_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    details_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # TIMEOUT, CREATOR_ABORT
    cancelled_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


__all__ = ["NatActiveSabotage"]
