from datetime import datetime
from sqlalchemy import (
    Integer, String, BigInteger, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base

class NatAlliance(Base):
    __tablename__ = "nat_alliances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    leader_company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Strictly enforced: maximum 3 members
    member_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_members: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    
    total_army_strength: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NatAllianceMember(Base):
    __tablename__ = "nat_alliance_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_alliances.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    role: Mapped[str] = mapped_column(String(20), default="MEMBER", nullable=False)  # LEADER, OFFICER, MEMBER
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
