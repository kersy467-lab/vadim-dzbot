"""Permanent, specialization-specific output improvements purchased with PVC."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.company_constants import VALID_SPECIALIZATIONS
from backend.natbirzha.services.premium_service import PremiumService


MAX_LEVEL = 40
BONUS_PER_LEVEL = 0.05
LEGACY_LEVEL_COSTS = (80, 160, 320)
LATER_LEVEL_COST = 320
PRICE_SCHEDULE_DESCRIPTION = (
    "Первые уровни: 80 / 160 / 320 PVC; с 4-го по 40-й — 320 PVC за уровень."
)
INDUSTRY_PERKS: dict[str, tuple[str, str]] = {
    "agrarian": ("Точное земледелие", "Повышает выпуск сельскохозяйственных предприятий на 5% за уровень."),
    "miner": ("Умная добыча", "Повышает выпуск горнодобывающих предприятий на 5% за уровень."),
    "metallurgist": ("Металлургическая оптимизация", "Повышает выпуск металлургических предприятий на 5% за уровень."),
    "oilman": ("Интеллектуальное бурение", "Повышает выпуск нефтегазовых предприятий на 5% за уровень."),
    "power_engineer": ("Управление энергосетью", "Повышает выпуск энергетических предприятий на 5% за уровень."),
    "forester": ("Устойчивое лесопользование", "Повышает выпуск лесных предприятий на 5% за уровень."),
    "chemist": ("Химическая катализация", "Повышает выпуск химических предприятий на 5% за уровень."),
    "technoprom": ("Автоматизация технопрома", "Повышает выпуск технологических предприятий на 5% за уровень."),
    "water": ("Умные водные сети", "Повышает выпуск водоснабжения на 5% за уровень."),
    "construction": ("Поточная стройка", "Повышает выпуск строительных предприятий на 5% за уровень."),
    "logistics": ("Оптимизация маршрутов", "Повышает выпуск логистических предприятий на 5% за уровень. Не требует лития."),
}


class IndustryUpgradeService:
    @staticmethod
    def level_costs() -> list[int]:
        """Return the complete, bounded schedule while retaining legacy prices."""
        return [
            LEGACY_LEVEL_COSTS[level - 1] if level <= len(LEGACY_LEVEL_COSTS)
            else LATER_LEVEL_COST
            for level in range(1, MAX_LEVEL + 1)
        ]

    @classmethod
    def cost_for_level(cls, target_level: int) -> int:
        if target_level < 1 or target_level > MAX_LEVEL:
            raise ValueError("Уровень отраслевого улучшения вне допустимого диапазона")
        if target_level <= len(LEGACY_LEVEL_COSTS):
            return LEGACY_LEVEL_COSTS[target_level - 1]
        return LATER_LEVEL_COST

    @classmethod
    def catalog(cls) -> list[dict[str, Any]]:
        return [
            {
                "specialization": specialization,
                "code": f"industry_{specialization}",
                "title": INDUSTRY_PERKS[specialization][0],
                "description": INDUSTRY_PERKS[specialization][1],
                "max_level": MAX_LEVEL,
                "bonus_per_level_pct": BONUS_PER_LEVEL * 100,
                "max_bonus_pct": MAX_LEVEL * BONUS_PER_LEVEL * 100,
                "level_costs": cls.level_costs(),
                "price_schedule": PRICE_SCHEDULE_DESCRIPTION,
            }
            for specialization in VALID_SPECIALIZATIONS
        ]

    @staticmethod
    def level(company: NatCompany, specialization: str | None = None) -> int:
        industry = specialization or company.specialization
        levels = company.industry_upgrade_levels_json or {}
        return max(0, min(MAX_LEVEL, int(levels.get(industry, 0))))

    @classmethod
    def bonus_multiplier(cls, company: NatCompany, specialization: str | None = None) -> float:
        return 1.0 + cls.level(company, specialization) * BONUS_PER_LEVEL

    @classmethod
    def quote(cls, company: NatCompany) -> dict[str, Any]:
        specialization = company.specialization
        if specialization not in INDUSTRY_PERKS:
            return {"specialization": specialization, "available": False, "level": 0, "max_level": 0}
        level = cls.level(company)
        next_level = level + 1
        return {
            "available": True,
            "specialization": specialization,
            "code": f"industry_{specialization}",
            "title": INDUSTRY_PERKS[specialization][0],
            "description": INDUSTRY_PERKS[specialization][1],
            "level": level,
            "max_level": MAX_LEVEL,
            "bonus_pct": round(level * BONUS_PER_LEVEL * 100, 2),
            "max_bonus_pct": MAX_LEVEL * BONUS_PER_LEVEL * 100,
            "price_schedule": PRICE_SCHEDULE_DESCRIPTION,
            "next_bonus_pct": round(next_level * BONUS_PER_LEVEL * 100, 2) if level < MAX_LEVEL else None,
            "next_level_cost": cls.cost_for_level(next_level) if level < MAX_LEVEL else None,
            "pvc_balance": int(company.pvc_balance),
        }

    @classmethod
    async def purchase_next_level(
        cls,
        session: AsyncSession,
        company_id: int,
        operation_key: str,
        *,
        now: datetime | None = None,
        actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Компания не найдена")
        quote = cls.quote(company)
        if not quote.get("available"):
            raise ValueError("Для этой отрасли PVC-улучшение недоступно")
        if quote["level"] >= MAX_LEVEL:
            raise ValueError("Достигнут максимальный уровень отраслевого улучшения")
        cost = int(quote["next_level_cost"])
        await PremiumService.apply_pvc(
            session,
            company_id,
            -cost,
            "industry_upgrade",
            operation_key,
            {
                "specialization": company.specialization,
                "level": quote["level"] + 1,
                "bonus_pct": quote["next_bonus_pct"],
            },
            actor_user_id,
        )
        levels = dict(company.industry_upgrade_levels_json or {})
        levels[company.specialization] = quote["level"] + 1
        company.industry_upgrade_levels_json = levels
        await session.flush()
        result = cls.quote(company)
        result.update({"success": True, "cost_pvc": cost, "level": quote["level"] + 1})
        return result


__all__ = ["IndustryUpgradeService", "INDUSTRY_PERKS"]
