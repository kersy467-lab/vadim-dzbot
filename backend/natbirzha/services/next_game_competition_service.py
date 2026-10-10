"""Lazy company rankings for the closed NATBIRZHA 2.0 playtest."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameLedger
from backend.natbirzha.next_game_catalog import get_next_game_catalog, get_next_game_items
from backend.natbirzha.services.next_game_service.common import _utcnow


class NextGameCompetitionService:
    """Ranks companies by cash, development and actual production output."""

    @classmethod
    async def snapshot(
        cls, session: AsyncSession, owner_tg_id: int, *,
        now: datetime | None = None, limit: int = 10,
    ) -> dict[str, Any]:
        current = now or _utcnow()
        viewer = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.owner_tg_id == int(owner_tg_id),
        ))
        if viewer is None:
            raise ValueError("Сначала создай тестовую компанию")
        companies = list((await session.scalars(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id > 0).order_by(NatNextGameCompany.id)
        )).all())
        items = get_next_game_items()
        production_rows = list((await session.scalars(select(NatNextGameLedger).where(
            NatNextGameLedger.action.in_(("PRODUCTION_OUTPUT", "JOINT_OUTPUT")),
            NatNextGameLedger.created_at >= current - timedelta(hours=24),
        ).order_by(NatNextGameLedger.id))).all())
        production_value: dict[int, float] = {}
        for row in production_rows:
            item = items.get(row.item_id or "")
            if item is None:
                continue
            value = max(0.0, float(row.quantity_company_delta)) * float(item["base_price"])
            production_value[row.company_id] = production_value.get(row.company_id, 0.0) + value

        sectors = {sector["id"]: sector["name"] for sector in get_next_game_catalog()}
        rows = [{
            "company_id": int(company.id),
            "name": company.name,
            "sector_id": company.sector_id,
            "sector_name": sectors.get(company.sector_id, "Корпорация не выбрана"),
            "cash": round(float(company.cash), 2),
            "level": int(company.level),
            "xp": int(company.xp),
            "production_24h": round(production_value.get(company.id, 0.0), 2),
            "is_mine": company.id == viewer.id,
        } for company in companies]

        rankings = {}
        metrics = (
            ("cash", "Капитал", "cash", ("cash", "level", "xp", "name")),
            ("level", "Развитие", "level", ("level", "xp", "cash", "name")),
            ("production_24h", "Выпуск за 24 часа", "production_24h", ("production_24h", "level", "name")),
        )
        for metric_id, title, value_field, sort_fields in metrics:
            ordered = sorted(rows, key=lambda row: (
                *( -float(row[field]) for field in sort_fields if field != "name"),
                row["name"].casefold(),
            ))
            ranked = [{**row, "rank": index + 1, "value": row[value_field]}
                      for index, row in enumerate(ordered)]
            mine = next((row for row in ranked if row["is_mine"]), None)
            rankings[metric_id] = {
                "title": title,
                "leaders": ranked[:max(1, min(20, int(limit)))],
                "my_rank": mine,
            }
        return {
            "generated_at": current.isoformat(),
            "company_count": len(rows),
            "rankings": rankings,
        }


__all__ = ["NextGameCompetitionService"]
