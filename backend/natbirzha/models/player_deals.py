"""Bilateral, time-limited supply deals between player companies."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatSupplyDeal(Base):
    __tablename__ = "nat_supply_deals"
    __table_args__ = (
        Index("ix_nat_supply_deals_buyer_status", "buyer_company_id", "status"),
        Index("ix_nat_supply_deals_supplier_status", "supplier_company_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    supplier_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reward_type: Mapped[str] = mapped_column(String(24), nullable=False)
    profit_share_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fixed_cash: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    term_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    quoted_reference_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    settlement_cursor: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    resource_cash_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    profit_share_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fixed_cash_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class NatSupplyDealSettlement(Base):
    __tablename__ = "nat_supply_deal_settlements"
    __table_args__ = (
        UniqueConstraint("deal_id", "idempotency_key", name="uq_nat_supply_deal_settlement_key"),
        Index("ix_nat_supply_deal_settlements_period", "deal_id", "period_start", "period_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_supply_deals.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    settlement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    business_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nat_businesses.id", ondelete="SET NULL"), nullable=True
    )
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    market_reference_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cash_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    profit_base_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


__all__ = ["NatSupplyDeal", "NatSupplyDealSettlement"]
