"""Shared state-funded city orders and their auditable delivery ledger."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatCityOrderCycleState(Base):
    __tablename__ = "nat_city_order_cycle_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cycle_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pending_industries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    issued_industries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_scheduled_slot: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NatCityOrder(Base):
    __tablename__ = "nat_city_orders"
    __table_args__ = (UniqueConstraint("scheduled_slot", name="uq_nat_city_order_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheduled_slot: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    reserved_cash: Mapped[float] = mapped_column(Float, nullable=False)
    paid_cash: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatCityOrderDelivery(Base):
    __tablename__ = "nat_city_order_deliveries"
    __table_args__ = (
        UniqueConstraint("company_id", "order_id", "idempotency_key", name="uq_nat_city_delivery_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_city_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    seller_industry: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    cash_amount: Mapped[float] = mapped_column(Float, nullable=False)
    cost_of_goods_sold: Mapped[float] = mapped_column(Float, nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


__all__ = ["NatCityOrder", "NatCityOrderCycleState", "NatCityOrderDelivery"]
