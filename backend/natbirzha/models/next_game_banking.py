"""Corporate bank accounts and fee-backed payments for NATBIRZHA 2.0."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NatNextGameBankAccount(Base):
    __tablename__ = "nat_next_game_bank_accounts"
    __table_args__ = (
        UniqueConstraint("bank_company_id", "customer_company_id", name="uq_next_game_bank_customer"),
        CheckConstraint("bank_company_id <> customer_company_id", name="ck_next_game_bank_not_self"),
        CheckConstraint("status IN ('ACTIVE', 'CLOSED')", name="ck_next_game_bank_account_status"),
        Index("ix_next_game_bank_accounts_customer", "customer_company_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False,
    )
    customer_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameBankPayment(Base):
    __tablename__ = "nat_next_game_bank_payments"
    __table_args__ = (
        UniqueConstraint("bank_company_id", "idempotency_key", name="uq_next_game_bank_payment_key"),
        CheckConstraint("payer_company_id <> payee_company_id", name="ck_next_game_bank_payment_distinct"),
        CheckConstraint("amount >= 100", name="ck_next_game_bank_payment_minimum"),
        CheckConstraint("fee >= 0", name="ck_next_game_bank_payment_fee_nonnegative"),
        Index("ix_next_game_bank_payment_time", "bank_company_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    payer_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_bank_accounts.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    payee_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_bank_accounts.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    payer_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    payee_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)


class NatNextGameCorporateLoan(Base):
    __tablename__ = "nat_next_game_corporate_loans"
    __table_args__ = (
        UniqueConstraint("bank_company_id", "idempotency_key", name="uq_next_game_corp_loan_key"),
        CheckConstraint("bank_company_id <> borrower_company_id", name="ck_next_game_corp_loan_distinct"),
        CheckConstraint("principal >= 1000", name="ck_next_game_corp_loan_minimum"),
        CheckConstraint("daily_rate >= 0 AND maturity_amount >= principal", name="ck_next_game_corp_loan_terms"),
        CheckConstraint("term_days BETWEEN 1 AND 30", name="ck_next_game_corp_loan_term"),
        CheckConstraint("status IN ('ACTIVE', 'PAID')", name="ck_next_game_corp_loan_status"),
        Index("ix_next_game_corp_loan_borrower", "borrower_company_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    borrower_company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_next_game_companies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    principal: Mapped[float] = mapped_column(Float, nullable=False)
    daily_rate: Mapped[float] = mapped_column(Float, nullable=False)
    term_days: Mapped[int] = mapped_column(Integer, nullable=False)
    maturity_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    repayment_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repaid_amount: Mapped[float | None] = mapped_column(Float, nullable=True)


__all__ = [
    "NatNextGameBankAccount", "NatNextGameBankPayment", "NatNextGameCorporateLoan",
]
