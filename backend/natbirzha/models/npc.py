from datetime import date

from sqlalchemy import Date, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base


class NatNpcDailyVolume(Base):
    __tablename__ = "nat_npc_daily_volume"
    __table_args__ = (
        UniqueConstraint("calendar_date", "item_id", "action", name="uq_nat_npc_daily_item_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    used_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


__all__ = ["NatNpcDailyVolume"]
