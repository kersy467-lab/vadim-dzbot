from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Integer, String, Float, DateTime,
    ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base

class NatMarketOrder(Base):
    __tablename__ = "nat_market_orders"
    __table_args__ = (
        Index("ix_nat_orders_item_status_price", "item_id", "status", "price"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY or SELL
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_qty: Mapped[float] = mapped_column(Float, nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)  # ACTIVE, FILLED, CANCELLED
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class NatMarketTrade(Base):
    __tablename__ = "nat_market_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buy_order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("nat_market_orders.id", ondelete="SET NULL"), nullable=True)
    sell_order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("nat_market_orders.id", ondelete="SET NULL"), nullable=True)
    
    buyer_company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
