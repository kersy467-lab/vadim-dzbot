"""Isolated settings, corporate aid and administrator audit records."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NatNextGameProfile(Base):
    __tablename__ = "nat_next_game_profiles"
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), primary_key=True)
    auto_upgrade: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rebirths: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pvc_balance: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    pvc_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_auto_upgrade_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameHelpRequest(Base):
    __tablename__ = "nat_next_game_help_requests"
    __table_args__ = (CheckConstraint("goal > 0 AND received >= 0 AND received <= goal", name="ck_next_aid_amount"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    goal: Mapped[float] = mapped_column(Float, nullable=False)
    received: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    description: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class NatNextGameTransfer(Base):
    __tablename__ = "nat_next_game_transfers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    recipient_company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    cash: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class NatNextGameAdminAudit(Base):
    __tablename__ = "nat_next_game_admin_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
