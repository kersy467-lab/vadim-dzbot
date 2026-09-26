"""Daily operating-profit tax liabilities for NATBIRZHA companies."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
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
    """12-hour game period tax liability with +3%/hour simple overdue penalty."""

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


class NatCompanyProfitPeriod(Base):
    """Company-wide realized net result for one 12-hour tax period."""

    __tablename__ = "nat_company_profit_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "period_start", name="uq_nat_company_profit_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    realized_revenue: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    financial_income: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0", nullable=False
    )
    cost_of_goods_sold: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    maintenance_expense: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    salary_expense: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    other_expenses: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Existing tax periods are frozen at rollout: their assessed liability is
    # carried forward even when the old ledger cannot identify realized sales.
    legacy_taxable_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        server_default=func.now(), nullable=False,
    )

    @property
    def net_profit(self) -> float:
        if self.legacy_taxable_profit is not None:
            return float(self.legacy_taxable_profit)
        return (
            float(self.realized_revenue or 0.0)
            + float(self.financial_income or 0.0)
            - float(self.cost_of_goods_sold or 0.0)
            - float(self.maintenance_expense or 0.0)
            - float(self.salary_expense or 0.0)
            - float(self.other_expenses or 0.0)
        )

    @property
    def operating_profit(self) -> float:
        """Compatibility alias; tax is assessed on total realized net profit."""
        return self.net_profit


__all__ = ["NatTaxDaily", "NatTaxPeriod", "NatCompanyProfitPeriod"]
