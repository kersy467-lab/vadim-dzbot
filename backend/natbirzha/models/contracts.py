from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Integer, String, Float, DateTime, Date,
    ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base

class NatContract(Base):
    __tablename__ = "nat_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_type: Mapped[str] = mapped_column(String(20), default="NPC", nullable=False)  # NPC or CORP
    
    issuer_company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    target_company_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    delivered_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    reward_cash: Mapped[float] = mapped_column(Float, nullable=False)
    reward_nat: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True)  # OPEN, ACTIVE, COMPLETED, FAILED
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatLoan(Base):
    __tablename__ = "nat_loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_debt: Mapped[float] = mapped_column(Float, nullable=False)
    daily_interest_rate: Mapped[float] = mapped_column(Float, default=0.01, nullable=False)
    
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)  # ACTIVE, PAID, DEFAULTED
    last_accrued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
