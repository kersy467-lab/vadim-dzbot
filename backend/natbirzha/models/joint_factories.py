"""Bilateral ownership, lifecycle and settlement ledger for joint factories."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatJointFactory(Base):
    __tablename__ = "nat_joint_factories"
    __table_args__ = (
        CheckConstraint("company_a_id <> company_b_id", name="ck_nat_joint_factory_distinct_owners"),
        CheckConstraint("level BETWEEN 1 AND 4", name="ck_nat_joint_factory_level"),
        CheckConstraint("status IN ('ACTIVE', 'CLOSED', 'BREACHED')", name="ck_nat_joint_factory_status"),
        Index(
            "uq_nat_joint_factory_owner_a_active", "company_a_id", unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uq_nat_joint_factory_owner_b_active", "company_b_id", unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_nat_joint_factory_status_cursor", "status", "last_settled_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    company_a_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    company_b_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    stock_a_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    stock_b_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    total_produced_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    claimed_a_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    claimed_b_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    total_cash_contributed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_resource_contributed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_settled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class NatJointFactoryProposal(Base):
    __tablename__ = "nat_joint_factory_proposals"
    __table_args__ = (
        CheckConstraint("operation IN ('BUILD', 'UPGRADE')", name="ck_nat_joint_factory_proposal_operation"),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
            name="ck_nat_joint_factory_proposal_status",
        ),
        Index("ix_nat_joint_factory_proposals_recipient_status", "partner_company_id", "status"),
        Index("ix_nat_joint_factory_proposals_sender_status", "proposer_company_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposer_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    partner_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    recipe_id: Mapped[str] = mapped_column(String(80), nullable=False)
    operation: Mapped[str] = mapped_column(String(16), default="BUILD", nullable=False)
    factory_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nat_joint_factories.id", ondelete="SET NULL"), nullable=True
    )
    target_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class NatJointFactorySettlement(Base):
    __tablename__ = "nat_joint_factory_settlements"
    __table_args__ = (
        UniqueConstraint(
            "factory_id", "period_start", "period_end",
            name="uq_nat_joint_factory_settlement_period",
        ),
        Index("ix_nat_joint_factory_settlements_period", "factory_id", "period_start", "period_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_joint_factories.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quantity_by_item_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


__all__ = ["NatJointFactory", "NatJointFactoryProposal", "NatJointFactorySettlement"]
