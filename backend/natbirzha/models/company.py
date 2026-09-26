from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Integer, String, Float, Boolean, DateTime, JSON,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.models import Base

class NatCompany(Base):
    __tablename__ = "nat_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    specialization: Mapped[str] = mapped_column(String(50), nullable=False)  # agrarian, miner, metallurgist, oilman, power_engineer, forester, chemist, technoprom
    
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_points_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_industry: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_logistics: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_doctrine: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_intelligence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cash: Mapped[float] = mapped_column(Float, default=10000.0, nullable=False)
    nat_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pvc_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    military_rating: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    
    territory_tiles: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    max_territory: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    business_slot_capacity: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    business_slot_upgrade_ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    industry_upgrade_levels_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    
    is_bankrupt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_respec_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    licensed_foreign_spec: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    custom_ticker: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    factories: Mapped[List["NatFactory"]] = relationship("NatFactory", back_populates="company", cascade="all, delete-orphan")

    @property
    def ticker(self) -> str:
        if self.custom_ticker and len(self.custom_ticker.strip()) >= 2:
            return self.custom_ticker.strip().upper()[:5]
        words = self.name.split()
        if len(words) >= 2:
            letters = "".join(w[0] for w in words if w).upper()
            if len(letters) >= 2:
                return letters[:5]
        clean = "".join(c for c in self.name if c.isalnum()).upper()
        return clean[:5] if len(clean) >= 3 else f"NAT{self.id}"


class NatFactory(Base):
    __tablename__ = "nat_factories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    building_type: Mapped[str] = mapped_column(String(100), nullable=False)  # farm, mine, refinery, tpp, smelter, sawmill, chem_plant, electronics_fab
    specialization: Mapped[str] = mapped_column(String(50), nullable=False)   # industry this factory belongs to
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Efficiency: 1.0 (100%), 0.10 (10%), max 0.12 (with license)
    efficiency: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    workers: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    automation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    automation_status: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False)
    automation_pause_reason: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    technology_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bankruptcy_acquired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    current_recipe: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cycle_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cycle_ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cycle_input_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Snapshot of the total multiplier funded by inputs when this cycle began.
    # Nullable for cycles already in progress when the migration is deployed.
    cycle_output_multiplier: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    last_produced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    company: Mapped["NatCompany"] = relationship("NatCompany", back_populates="factories")
