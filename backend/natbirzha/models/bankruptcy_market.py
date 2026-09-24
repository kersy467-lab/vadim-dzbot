"""Confiscated factory lots offered to players after creator bankruptcy."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatBankruptcyMarketLot(Base):
    __tablename__ = "nat_bankruptcy_market_lots"
    __table_args__ = (Index("ix_nat_bankruptcy_lots_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    former_company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    former_company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    industry: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost_basis: Mapped[float] = mapped_column(Float, nullable=False)
    ask_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)
    buyer_company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


__all__ = ["NatBankruptcyMarketLot"]
