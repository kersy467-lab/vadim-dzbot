"""Premium currency ledger and time-limited production licenses."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatPremiumLedgerEntry(Base):
    __tablename__ = "nat_premium_ledger"
    __table_args__ = (
        UniqueConstraint("operation_key", name="uq_nat_premium_ledger_operation_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    operation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatPremiumLicense(Base):
    __tablename__ = "nat_premium_licenses"
    __table_args__ = (
        UniqueConstraint("company_id", "license_code", name="uq_nat_premium_license_company_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    license_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)
    purchase_ledger_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_premium_ledger.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NatMilitaryUpgrade(Base):
    __tablename__ = "nat_military_upgrades"
    __table_args__ = (
        UniqueConstraint("company_id", "upgrade_code", name="uq_nat_military_upgrade_company_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    upgrade_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
