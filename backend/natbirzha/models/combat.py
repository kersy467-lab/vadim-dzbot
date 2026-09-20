"""Normalized combat, PvE war, rating, and PvP cooldown models."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatArmyUnit(Base):
    __tablename__ = "nat_army_units"
    __table_args__ = (
        UniqueConstraint("company_id", "unit_type", name="uq_nat_army_unit_company_type"),
        CheckConstraint("quantity >= 0", name="ck_nat_army_unit_quantity_nonnegative"),
        CheckConstraint("readiness >= 0 AND readiness <= 10000", name="ck_nat_army_unit_readiness"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    readiness: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    experience: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NatPveCorporation(Base):
    __tablename__ = "nat_pve_corporations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    min_company_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prerequisite_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    premium_modifiers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    territory_reward: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cash_reward: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resource_rewards: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(32), default="p2-v1", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class NatBattle(Base):
    __tablename__ = "nat_battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attacker_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    defender_company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    pve_corporation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_pve_corporations.id", ondelete="RESTRICT"), nullable=True
    )
    tournament_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_tournaments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    winner_side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    seed_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(32), default="p2-v1", nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatBattleSnapshot(Base):
    __tablename__ = "nat_battle_snapshots"
    __table_args__ = (
        UniqueConstraint("battle_id", "side", name="uq_nat_battle_snapshot_side"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    battle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_battles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    modifiers_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    strength: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatPveVictory(Base):
    __tablename__ = "nat_pve_victories"
    __table_args__ = (
        UniqueConstraint("company_id", "pve_corporation_id", name="uq_nat_pve_victory_company_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pve_corporation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_pve_corporations.id", ondelete="CASCADE"), nullable=False
    )
    battle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_battles.id", ondelete="RESTRICT"), nullable=False
    )
    reward_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conquered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatMilitaryRatingEvent(Base):
    __tablename__ = "nat_military_rating_events"
    __table_args__ = (
        UniqueConstraint("battle_id", "company_id", name="uq_nat_rating_event_battle_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    battle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_battles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating_before: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_after: Mapped[int] = mapped_column(Integer, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatPvpCooldown(Base):
    __tablename__ = "nat_pvp_cooldowns"
    __table_args__ = (
        UniqueConstraint(
            "tournament_id", "attacker_company_id", "defender_company_id",
            name="uq_nat_pvp_cooldown_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attacker_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    defender_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    battle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_battles.id", ondelete="CASCADE"), nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
