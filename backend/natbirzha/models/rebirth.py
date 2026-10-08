"""Immutable audit of explicitly confirmed company rebirths."""
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base


class NatCompanyRebirth(Base):
    __tablename__ = 'nat_company_rebirths'
    __table_args__ = (UniqueConstraint('company_id', 'rank', name='uq_nat_company_rebirth_rank'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey('nat_companies.id', ondelete='CASCADE'), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_before: Mapped[float] = mapped_column(Float, nullable=False)
    tax_paid: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
