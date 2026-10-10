"""Server-authored activity sessions for the isolated NATBIRZHA 2.0 game."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base
from backend.natbirzha.models.next_game import _utcnow


class NatNextGameActiveSession(Base):
    __tablename__ = "nat_next_game_active_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'STOPPED', 'EXPIRED')",
            name="ck_next_game_active_session_status",
        ),
        Index("ix_next_game_active_company_status", "company_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[int] = mapped_column(
        ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    sector_id: Mapped[str] = mapped_column(String(48), nullable=False)
    selected_branch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_ping_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_user_input_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scene_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    skill_charge: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    hit_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    wheel_angle: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    wheel_direction: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    target_angle: Mapped[float] = mapped_column(Float, nullable=False, default=180, server_default="180")
    target_bars_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="'[]'")
    last_skill_tap_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


class NatNextGameActiveInterval(Base):
    __tablename__ = "nat_next_game_active_intervals"
    __table_args__ = (
        CheckConstraint("end_at >= start_at", name="ck_next_game_active_interval_order"),
        UniqueConstraint("session_id", "pulse_seq", name="uq_next_game_active_interval_pulse"),
        Index("ix_next_game_active_interval_company_time", "company_id", "start_at", "end_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("nat_next_game_active_sessions.id", ondelete="CASCADE"), nullable=False,
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pulse_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    output_multiplier: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.5, server_default="1.5",
    )
    reason: Mapped[str] = mapped_column(String(24), nullable=False, default="heartbeat")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


__all__ = ["NatNextGameActiveSession", "NatNextGameActiveInterval"]
