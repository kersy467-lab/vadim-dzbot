"""Post-level-60 mastery: endless choices with capped, diminishing effects."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.progression_service import progress_snapshot


BRANCHES: dict[str, dict[str, Any]] = {
    "industry": {
        "name": "Промышленная эффективность",
        "description": "Снижает стоимость строительства и модернизации.",
        "cap": 0.12,
        "scale": 8.0,
    },
    "logistics": {
        "name": "Территориальная логистика",
        "description": "Снижает стоимость следующего расширения территории.",
        "cap": 0.15,
        "scale": 8.0,
    },
    "doctrine": {
        "name": "Военная доктрина",
        "description": "Снижает cash-стоимость пополнения армии.",
        "cap": 0.15,
        "scale": 10.0,
    },
    "intelligence": {
        "name": "Разведка",
        "description": "Сужает погрешность разведданных по PvE-целям.",
        "cap": 0.50,
        "scale": 7.0,
    },
}


class MasteryService:
    @staticmethod
    def _attr(branch: str) -> str:
        if branch not in BRANCHES:
            raise ValueError("Unknown mastery branch")
        return f"mastery_{branch}"

    @classmethod
    def level(cls, company: NatCompany, branch: str) -> int:
        return max(0, int(getattr(company, cls._attr(branch), 0) or 0))

    @staticmethod
    def node_cost(current_level: int) -> int:
        """Each five purchased nodes make the next node cost one extra point."""
        return 1 + max(0, int(current_level)) // 5

    @classmethod
    def effect(cls, company: NatCompany, branch: str) -> float:
        """Hyperbolic diminishing return that approaches, but never exceeds, a cap."""
        spec = BRANCHES[branch]
        level = cls.level(company, branch)
        if level <= 0:
            return 0.0
        return round(float(spec["cap"]) * level / (level + float(spec["scale"])), 6)

    @classmethod
    def snapshot(cls, company: NatCompany) -> dict[str, Any]:
        progression = progress_snapshot(company)["mastery"]
        spent = max(0, int(getattr(company, "mastery_points_spent", 0) or 0))
        rank = int(progression["rank"])
        branches = {}
        for code, spec in BRANCHES.items():
            current = cls.level(company, code)
            branches[code] = {
                "code": code,
                "name": spec["name"],
                "description": spec["description"],
                "level": current,
                "next_cost": cls.node_cost(current),
                "effect_pct": round(cls.effect(company, code) * 100, 2),
                "cap_pct": round(float(spec["cap"]) * 100, 2),
            }
        return {
            **progression,
            "points_earned": rank,
            "points_spent": spent,
            "points_available": max(0, rank - spent),
            "branches": branches,
        }

    @classmethod
    async def unlock(cls, session: AsyncSession, company: NatCompany, branch: str) -> dict[str, Any]:
        if branch not in BRANCHES:
            raise ValueError("Неизвестная ветка мастерства")
        locked = await session.scalar(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )
        if locked is None:
            raise ValueError("Компания не найдена")
        if int(locked.level or 1) < 60:
            raise ValueError("Мастерство открывается после достижения 60 уровня")
        snapshot = cls.snapshot(locked)
        current = cls.level(locked, branch)
        cost = cls.node_cost(current)
        if snapshot["points_available"] < cost:
            raise ValueError(f"Недостаточно очков мастерства: нужно {cost}")
        setattr(locked, cls._attr(branch), current + 1)
        locked.mastery_points_spent = int(getattr(locked, "mastery_points_spent", 0) or 0) + cost
        await session.flush()
        return {"success": True, "branch": branch, "cost": cost, "mastery": cls.snapshot(locked)}


__all__ = ["BRANCHES", "MasteryService"]
