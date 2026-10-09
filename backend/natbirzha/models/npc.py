from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatNpcDailyVolume(Base):
    __tablename__ = "nat_npc_daily_volume"
    __table_args__ = (
        UniqueConstraint("calendar_date", "item_id", "action", name="uq_nat_npc_daily_item_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    used_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    used_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class NatNpcCompanyDailyVolume(Base):
    """Per-company cash already paid by the State reserve for capped items."""

    __tablename__ = "nat_npc_company_daily_volume"
    __table_args__ = (
        UniqueConstraint(
            "calendar_date", "company_id", "item_id",
            name="uq_nat_npc_company_daily_item",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    used_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class NatStateReserveStock(Base):
    """Resources bought by the State from companies and available for export."""

    __tablename__ = "nat_state_reserve_stock"

    item_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_cost_basis: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


__all__ = ["NatNpcDailyVolume", "NatNpcCompanyDailyVolume", "NatStateReserveStock"]
