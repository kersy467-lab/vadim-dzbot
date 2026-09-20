"""Persistent military infrastructure and asynchronous training foundation."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatMilitaryInfrastructure(Base):
    __tablename__ = "nat_military_infrastructure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    command_center_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    barracks_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    armor_base_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    airbase_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    air_defense_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    logistics_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    intelligence_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class NatArmyTraining(Base):
    __tablename__ = "nat_army_trainings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ready_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="TRAINING", nullable=False, index=True)


__all__ = ["NatMilitaryInfrastructure", "NatArmyTraining"]
