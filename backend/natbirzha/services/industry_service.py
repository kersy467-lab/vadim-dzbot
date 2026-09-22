"""Industry population pressure for the company creation screen."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import INDUSTRIES, starter_business_spec
from backend.natbirzha.models.company import NatCompany


class IndustryService:
    @staticmethod
    def _status(count: int, total: int, target_share: float) -> tuple[str, str, str]:
        target = max(1.0, max(total, 1) * float(target_share))
        saturation = count / target
        if count == 0:
            return "green", "Критически востребована", "На сервере пока нет компаний этой отрасли."
        if saturation < 0.80:
            return "green", "Рекомендуется", "Компаний меньше целевого уровня, спросу нужен новый поставщик."
        if saturation < 1.35:
            return "yellow", "Сбалансировано", "Отрасль уже представлена, но место для конкуренции есть."
        return "red", "Высокая конкуренция", "Компаний этой отрасли заметно больше целевого уровня."

    @classmethod
    async def overview(cls, session: AsyncSession) -> dict:
        rows = (await session.execute(
            select(NatCompany.specialization, func.count(NatCompany.id))
            .group_by(NatCompany.specialization)
        )).all()
        counts = {str(spec): int(count) for spec, count in rows}
        total = sum(counts.values())
        items = []
        for industry_id, meta in INDUSTRIES.items():
            count = counts.get(industry_id, 0)
            color, label, hint = cls._status(count, total, float(meta["target_share"]))
            starter = starter_business_spec(industry_id)
            items.append({
                "id": industry_id,
                "name": meta["name"],
                "icon": meta["icon"],
                "summary": meta["summary"],
                "difficulty": int(meta["difficulty"]),
                "company_count": count,
                "target_share": float(meta["target_share"]),
                "status_color": color,
                "status_label": label,
                "status_hint": hint,
                "starter_business": starter["name"] if starter else None,
                "starter_business_id": starter["id"] if starter else None,
            })
        color_order = {"green": 0, "yellow": 1, "red": 2}
        items.sort(key=lambda item: (color_order[item["status_color"]], item["company_count"], item["name"]))
        return {"total_companies": total, "items": items}


__all__ = ["IndustryService"]
