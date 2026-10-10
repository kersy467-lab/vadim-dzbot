"""Explicit beta bankruptcies, debt loss audit and bank owned factory lots."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base


class NatNextGameBankruptcy(Base):
    __tablename__ = "nat_next_game_bankruptcies"
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), primary_key=True)
    requires_ack: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    was_triggered: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False)
    creator_tg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recovery_choice: Mapped[str | None] = mapped_column(String(16), nullable=True)


class NatNextGameLiquidationLot(Base):
    __tablename__ = "nat_next_game_liquidation_lots"
    __table_args__ = (CheckConstraint("price > 0 AND level BETWEEN 1 AND 10", name="ck_next_liquidation_terms"),
        CheckConstraint("status IN ('OPEN','SOLD')", name="ck_next_liquidation_status"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    bankruptcy_sequence: Mapped[int] = mapped_column(Integer)
    branch_id: Mapped[str] = mapped_column(String(64))
    level: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="OPEN")
    buyer_company_id: Mapped[int | None] = mapped_column(ForeignKey("nat_next_game_companies.id"), nullable=True)
    listed_at: Mapped[datetime] = mapped_column(DateTime)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameDebtWriteoff(Base):
    __tablename__ = "nat_next_game_debt_writeoffs"
    __table_args__ = (UniqueConstraint("kind", "obligation_id", name="uq_next_writeoff_obligation"),
        CheckConstraint("amount >= 0", name="ck_next_writeoff_nonnegative"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    creditor_company_id: Mapped[int | None] = mapped_column(ForeignKey("nat_next_game_companies.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    obligation_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime)
