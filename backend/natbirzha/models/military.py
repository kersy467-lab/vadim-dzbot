from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Integer, BigInteger, String, DateTime,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base

class NatArmy(Base):
    __tablename__ = "nat_armies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    infantry: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tanks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    drones: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    air_defense: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Army strength calculated as: infantry*10 + tanks*150 + drones*80 + air_defense*200
    army_strength: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NatTournament(Base):
    __tablename__ = "nat_tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    finish_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, SNAPSHOT, COMPLETED
    prize_pool_nat: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    tournament_type: Mapped[str] = mapped_column(String(20), default="AUTO", nullable=False)
    reward_first_pvc: Mapped[int] = mapped_column(Integer, default=150, nullable=False)
    reward_second_pvc: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    reward_third_pvc: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def cycle_number(self) -> int:
        return self.tournament_number



class NatTournamentParticipant(Base):
    __tablename__ = "nat_tournament_participants"
    __table_args__ = (
        UniqueConstraint("tournament_id", "company_id", name="uq_nat_tournament_participant"),
        Index("ix_nat_tournament_ranking", "tournament_id", "snapshot_strength", "army_updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_tournaments.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    alliance_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Snapshot values taken exactly at snapshot_time (Immutable)
    snapshot_strength: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    initial_strength: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    final_strength: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    initial_rating: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    final_rating: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    army_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    final_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prize_nat: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prize_pvc: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
