"""Supply escrow and joint production belong exclusively to the 2.0 economy."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NatNextGameSupplyDeal(Base):
    __tablename__ = "nat_next_game_supply_deals"
    __table_args__ = (
        CheckConstraint("buyer_company_id <> seller_company_id", name="ck_next_supply_parties"),
        CheckConstraint("quantity > 0 AND delivered >= 0 AND delivered <= quantity", name="ck_next_supply_quantity"),
        CheckConstraint("unit_price > 0 AND rate_per_hour > 0 AND escrow_cash >= 0", name="ck_next_supply_terms"),
        CheckConstraint("status IN ('OPEN','ACTIVE','COMPLETED','CANCELLED','EXPIRED')", name="ck_next_supply_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    seller_company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    delivered: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    rate_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    escrow_cash: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    blocked_reason: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    offered_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NatNextGameJointProject(Base):
    __tablename__ = "nat_next_game_joint_projects"
    __table_args__ = (
        CheckConstraint("proposer_company_id <> partner_company_id", name="ck_next_project_parties"),
        CheckConstraint("build_cost > 0 AND escrow_cash >= 0", name="ck_next_project_cost"),
        CheckConstraint("status IN ('OPEN','ACTIVE','CANCELLED')", name="ck_next_project_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposer_company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    partner_company_id: Mapped[int] = mapped_column(ForeignKey("nat_next_game_companies.id"), index=True)
    branch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    recipe_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    build_cost: Mapped[float] = mapped_column(Float, nullable=False)
    escrow_cash: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    cycles_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_reason: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    offered_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_cycle_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


__all__ = ["NatNextGameSupplyDeal", "NatNextGameJointProject"]
