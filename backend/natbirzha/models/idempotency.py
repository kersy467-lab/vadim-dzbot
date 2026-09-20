from datetime import datetime
from sqlalchemy import (
    Integer, BigInteger, String, DateTime,
    JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base

class NatIdempotencyRecord(Base):
    __tablename__ = "nat_idempotency_records"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", "idempotency_key", name="uq_nat_idempotency_user_ep_key"),
        Index("ix_nat_idempotency_lookup", "user_id", "endpoint", "idempotency_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hex of payload
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
