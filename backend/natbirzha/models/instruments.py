from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatReferenceRateSnapshot(Base):
    __tablename__ = "nat_reference_rate_snapshots"
    __table_args__ = (
        UniqueConstraint("instrument_code", "quoted_at", "source_id", name="uq_nat_reference_rate_quote"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    value_rub: Mapped[float] = mapped_column(Float, nullable=False)
    nominal: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_id: Mapped[str] = mapped_column(String(30), default="cbr", nullable=False)
    source_url: Mapped[str] = mapped_column(String(255), nullable=False)
    quoted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class NatInstrumentPosition(Base):
    __tablename__ = "nat_instrument_positions"
    __table_args__ = (
        UniqueConstraint("company_id", "instrument_code", name="uq_nat_instrument_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_cost_rub: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatInstrumentTrade(Base):
    __tablename__ = "nat_instrument_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_rub: Mapped[float] = mapped_column(Float, nullable=False)
    gross_rub: Mapped[float] = mapped_column(Float, nullable=False)
    spread_rub: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    position_after: Mapped[float] = mapped_column(Float, nullable=False)
    source_snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_reference_rate_snapshots.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


__all__ = ["NatReferenceRateSnapshot", "NatInstrumentPosition", "NatInstrumentTrade"]
