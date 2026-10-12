"""PVC cases and collectible employees for NATBIRZHA 2.0."""

from __future__ import annotations

import math
import secrets
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameLedger,
)
from backend.natbirzha.models.next_game_managers import NatNextGameManager
from backend.natbirzha.models.next_game_community import NatNextGameProfile
from backend.natbirzha.services.next_game_manager_service import (
    ensure_manager_awards,
    manager_payload,
)
from backend.natbirzha.services.next_game_service import NextGameService

CASE_PRICE_PVC = 25
CASE_DROP_ODDS = (
    {"rarity": "common", "probability": 0.70, "level_min": 1, "level_max": 10, "discount_pct": 2},
    {"rarity": "rare", "probability": 0.22, "level_min": 11, "level_max": 20, "discount_pct": 4},
    {"rarity": "epic", "probability": 0.07, "level_min": 21, "level_max": 30, "discount_pct": 6},
    {"rarity": "legendary", "probability": 0.01, "level_min": 31, "level_max": 50, "discount_pct": 8},
)

_FIRST_NAMES = (
    "Avery", "Jordan", "Riley", "Morgan", "Taylor", "Casey", "Jamie", "Cameron",
    "Quinn", "Parker", "Alex", "Drew", "Rowan", "Skyler", "Reese", "Finley",
)
_LAST_NAMES = (
    "Brooks", "Hayes", "Bennett", "Morgan", "Cole", "Reed", "Parker", "Foster",
    "Ellis", "Warren", "Blake", "Quinn", "Miller", "Carter", "Sullivan", "Bennett",
)


def _draw_case_employee() -> dict[str, Any]:
    """Draw a rarity by published odds, then a level within that tier."""
    roll = secrets.randbelow(10_000)
    cumulative = 0
    spec = CASE_DROP_ODDS[-1]
    for option in CASE_DROP_ODDS:
        cumulative += round(option["probability"] * 10_000)
        if roll < cumulative:
            spec = option
            break
    level = secrets.randbelow(spec["level_max"] - spec["level_min"] + 1) + spec["level_min"]
    name = f"{secrets.choice(_FIRST_NAMES)} {secrets.choice(_LAST_NAMES)}"
    return {**spec, "level": level, "name": name}


def _case_catalog() -> dict[str, Any]:
    return {
        "price_pvc": CASE_PRICE_PVC,
        "odds": [dict(row) for row in CASE_DROP_ODDS],
    }


class NextGameEmployeeService:
    """Owns the collectible workforce, case wallet debit, and safe deletion."""

    @staticmethod
    async def snapshot(session: AsyncSession, owner_tg_id: int) -> dict[str, Any]:
        company = await NextGameService._owned_company(session, owner_tg_id)
        employees = await ensure_manager_awards(session, company)
        facilities = list((await session.scalars(select(NatNextGameFacility).where(
            NatNextGameFacility.company_id == company.id,
        ))).all())
        branch_by_facility = {row.id: row.branch_id for row in facilities}
        wallet = await session.get(NatNextGameProfile, company.id)
        employees.sort(key=lambda row: (row.level, row.id))
        return {
            "company_id": company.id,
            "pvc_balance": float(wallet.pvc_balance or 0) if wallet else 0,
            "case": _case_catalog(),
            "employees": [
                manager_payload(row, branch_by_facility.get(row.facility_id))
                for row in employees
            ],
        }

    @staticmethod
    async def open_case(session: AsyncSession, owner_tg_id: int) -> dict[str, Any]:
        """Charge 25 profile PVC and award exactly one employee in this transaction."""
        await NextGameService._lock_treasury_for_sqlite(session)
        company = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.owner_tg_id == int(owner_tg_id),
        ).with_for_update().execution_options(populate_existing=True))
        if company is None:
            raise ValueError("Сначала создайте компанию 2.0")

        wallet = await session.scalar(select(NatNextGameProfile).where(
            NatNextGameProfile.company_id == company.id,
        ).with_for_update().execution_options(populate_existing=True))
        if wallet is None:
            wallet = NatNextGameProfile(
                company_id=company.id, auto_upgrade=False, rebirths=0,
                pvc_balance=0, pvc_level=0,
            )
            session.add(wallet)
            await session.flush()
        balance_before = float(wallet.pvc_balance or 0)
        if not math.isfinite(balance_before) or balance_before + 1e-8 < CASE_PRICE_PVC:
            available = max(0, balance_before) if math.isfinite(balance_before) else 0
            raise ValueError(f"Недостаточно PVC: нужно {CASE_PRICE_PVC} PVC, доступно {available:g}")

        await ensure_manager_awards(session, company)
        employee_roll = _draw_case_employee()
        odds = next((row for row in CASE_DROP_ODDS if row["rarity"] == employee_roll["rarity"]), None)
        level = int(employee_roll["level"])
        if odds is None or not odds["level_min"] <= level <= odds["level_max"]:
            raise ValueError("Не удалось определить уровень и редкость сотрудника")
        reward_sequence = int(await session.scalar(select(
            func.coalesce(func.max(NatNextGameManager.reward_level), 45)
        ).where(NatNextGameManager.company_id == company.id))) + 1
        employee = NatNextGameManager(
            company_id=company.id,
            reward_level=reward_sequence,
            name=employee_roll["name"],
            rarity=employee_roll["rarity"],
            discount_pct=int(odds["discount_pct"]),
            source="case",
            level=level,
        )
        wallet.pvc_balance = round(balance_before - CASE_PRICE_PVC, 4)
        session.add(employee)
        await session.flush()
        session.add(NextGameService._ledger(
            company.id, "EMPLOYEE_CASE_OPEN", 0, 0,
            metadata={
                "pvc_delta": -CASE_PRICE_PVC,
                "pvc_balance_before": balance_before,
                "pvc_balance_after": wallet.pvc_balance,
                "employee_id": employee.id,
                "employee_level": employee.level,
                "rarity": employee.rarity,
                "drop_probability": odds["probability"],
            },
        ))
        await session.flush()
        return {
            "success": True,
            "paid_pvc": CASE_PRICE_PVC,
            "pvc_balance": wallet.pvc_balance,
            "employee": manager_payload(employee),
            "drop_probability": odds["probability"],
        }

    @staticmethod
    async def delete_employee(
        session: AsyncSession, owner_tg_id: int, employee_id: int,
    ) -> dict[str, Any]:
        await NextGameService._lock_treasury_for_sqlite(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        employee = await session.scalar(select(NatNextGameManager).where(
            NatNextGameManager.id == int(employee_id),
            NatNextGameManager.company_id == company.id,
        ).with_for_update())
        if employee is None:
            raise ValueError("Сотрудник не найден в вашей компании")
        if employee.source != "case":
            raise ValueError("Гарантированных сотрудников за уровень нельзя удалить")
        if employee.facility_id is not None:
            raise ValueError("Сначала снимите назначенного сотрудника с завода")
        record = {
            "employee_id": employee.id,
            "name": employee.name,
            "level": employee.level,
            "rarity": employee.rarity,
        }
        await session.delete(employee)
        session.add(NextGameService._ledger(
            company.id, "EMPLOYEE_DELETE", 0, 0, metadata=record,
        ))
        await session.flush()
        return {"success": True, **record}


__all__ = ["CASE_PRICE_PVC", "CASE_DROP_ODDS", "NextGameEmployeeService"]
