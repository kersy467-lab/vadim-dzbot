"""Daily operating-profit tax liabilities for NATBIRZHA companies."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatTaxDaily(Base):
    """One immutable game-day tax base with mutable payment/penalty state."""

    __tablename__ = "nat_tax_daily"
    __table_args__ = (UniqueConstraint("company_id", "tax_date", name="uq_nat_tax_daily_company_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tax_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    taxable_profit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    principal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_penalty_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @property
    def total_assessed(self) -> float:
        return round(float(self.principal or 0.0) + float(self.penalty or 0.0), 2)

    @property
    def outstanding(self) -> float:
        return round(max(0.0, self.total_assessed - float(self.paid_amount or 0.0)), 2)


class NatTaxPeriod(Base):
    """12-hour game period tax liability with 12h grace and +3%/hour simple penalty."""

    __tablename__ = "nat_tax_periods"
    __table_args__ = (UniqueConstraint("company_id", "period_start", name="uq_nat_tax_period_company_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    taxable_profit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    principal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_penalty_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @property
    def total_assessed(self) -> float:
        return round(float(self.principal or 0.0) + float(self.penalty or 0.0), 2)

    @property
    def outstanding(self) -> float:
        return round(max(0.0, self.total_assessed - float(self.paid_amount or 0.0)), 2)


__all__ = ["NatTaxDaily", "NatTaxPeriod"]
