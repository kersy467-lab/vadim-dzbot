"""Explain the midgame capital decision without forcing a single strategy."""

from __future__ import annotations

from typing import Any

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.building_catalog import CANONICAL_BUILDINGS


IPO_RECOMMENDATION_LEVEL = 14
MIN_SELF_FUNDED_BUFFER = 90_000.0


def _next_own_project(company: NatCompany) -> dict[str, Any]:
    """Return the closest serious own-industry build target for a company."""

    candidates = [
        spec for spec in CANONICAL_BUILDINGS.values()
        if spec["specialization"] == company.specialization
        and int(spec["level_required"]) <= int(company.level)
    ]
    candidates.sort(key=lambda spec: (float(spec["build_cost"]), spec["name"]))
    affordable = [spec for spec in candidates if float(spec["build_cost"]) > company.cash]
    project = affordable[0] if affordable else (candidates[-1] if candidates else None)
    if not project:
        return {"name": "Расширение территории", "cost": 100_000.0, "level_required": company.level}
    return {
        "name": project["name"],
        "cost": round(float(project["build_cost"]), 2),
        "level_required": int(project["level_required"]),
    }


def capital_plan_for_company(company: NatCompany, *, is_public: bool) -> dict[str, Any]:
    """Build a concise, optional capital plan used by the overview screen."""

    cash = round(float(company.cash or 0.0), 2)
    if is_public:
        return {
            "state": "public",
            "recommended": False,
            "title": "Капитал уже привлечён",
            "message": "Компания публичная: развивайте производство и поддерживайте дивидендную политику.",
        }

    if int(company.level or 1) < IPO_RECOMMENDATION_LEVEL:
        return {
            "state": "grow_first",
            "recommended": False,
            "title": "Сначала укрепите производство",
            "message": f"IPO станет стратегическим вариантом после уровня {IPO_RECOMMENDATION_LEVEL}.",
        }

    project = _next_own_project(company)
    required_cash = max(MIN_SELF_FUNDED_BUFFER, float(project["cost"]))
    if cash >= required_cash:
        return {
            "state": "self_funded",
            "recommended": False,
            "title": "Проект можно профинансировать самостоятельно",
            "message": "У вас достаточно ликвидности. IPO остаётся доступным, но не требуется для следующего шага.",
            "project": project,
        }

    shortfall = round(max(0.0, required_cash - cash), 2)
    return {
        "state": "ipo_recommended",
        "recommended": True,
        "title": "Время привлечь капитал",
        "message": (
            f"Следующий проект — {project['name']} за {project['cost']:,.0f} cash. "
            "Можно копить, взять ограниченный кредит или привлечь капитал через IPO."
        ),
        "cash": cash,
        "cash_shortfall": shortfall,
        "project": project,
        "min_dividend_pct": float(nat_settings.IPO_MIN_DIVIDEND_PCT),
        "action": {"tab": "market", "label": "Сравнить IPO"},
        "debt_option": {
            "available_from_level": 14,
            "label": "Рассмотреть кредит",
            "tradeoff": "Без размытия доли, но с ежедневным процентом и сроком погашения.",
        },
        "alternative": "Накопление медленнее, кредит создаёт долговую нагрузку, IPO размывает долю и добавляет дивиденды.",
    }


__all__ = ["capital_plan_for_company"]
