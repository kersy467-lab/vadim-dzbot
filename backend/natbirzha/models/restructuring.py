from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base

class NatRestructuring(Base):
    __tablename__ = "nat_restructurings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Frozen snapshot values: 40% of audited NAV at the moment of filing
    snapshot_nav: Mapped[float] = mapped_column(Float, nullable=False)
    liquidation_pool: Mapped[float] = mapped_column(Float, nullable=False)  # Exactly 0.40 * snapshot_nav
    
    # Strictly next 2 real calendar dates in GAME_TIMEZONE
    fee_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    fee_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    fee_rate: Mapped[float] = mapped_column(Float, default=0.30, nullable=False)  # 30% of positive profit
    
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)  # ACTIVE or COMPLETED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatDailyFinancials(Base):
    __tablename__ = "nat_daily_financials"
    __table_args__ = (
        UniqueConstraint("company_id", "calendar_date", name="uq_nat_daily_financials_company_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    gross_revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    opex: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    closed_profit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    developer_fee_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    is_settled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
