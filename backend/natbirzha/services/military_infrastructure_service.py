"""Military infrastructure, async training and operational supply for War 2.0."""

from datetime import datetime, timedelta
from math import pow
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory, get_item_name
from backend.natbirzha.models.military_infrastructure import NatArmyTraining, NatMilitaryInfrastructure
from backend.natbirzha.services.army_service import ArmyService, RECRUITMENT_CATALOG
from backend.natbirzha.services.combat_resolver import ArmySnapshot
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


FACILITIES: Mapping[str, dict[str, Any]] = {
    "command_center": {"name": "Командный центр", "base_cash": 40_000.0, "items": {"steel": 20.0, "electronics": 2.0}},
    "barracks": {"name": "Казармы", "base_cash": 24_000.0, "items": {"steel": 12.0, "food": 20.0}},
    "armor_base": {"name": "Бронебаза", "base_cash": 90_000.0, "items": {"steel": 55.0, "fuel_diesel": 80.0}},
    "airbase": {"name": "Авиабаза", "base_cash": 240_000.0, "items": {"steel": 80.0, "electronics": 8.0, "jet_fuel": 100.0}},
    "air_defense": {"name": "Центр ПВО", "base_cash": 150_000.0, "items": {"steel": 60.0, "electronics": 10.0}},
    "logistics": {"name": "Военная логистика", "base_cash": 65_000.0, "items": {"fuel_diesel": 80.0, "food": 50.0}},
    "intelligence": {"name": "Разведцентр", "base_cash": 85_000.0, "items": {"electronics": 10.0, "sensors": 5.0}},
}

UNIT_REQUIREMENTS = {
    "infantry": ("barracks", 0), "border_guards": ("barracks", 1),
    "tanks": ("armor_base", 1), "drones": ("intelligence", 1),
    "aircraft": ("airbase", 1), "air_defense": ("air_defense", 1),
}

BASE_TRAIN_MINUTES = {
    "infantry": 1.2, "border_guards": 2.0, "tanks": 7.0,
    "drones": 3.0, "aircraft": 18.0, "air_defense": 10.0,
}


class MilitaryInfrastructureService:
    @staticmethod
    async def ensure(session: AsyncSession, company_id: int, *, for_update: bool = False) -> NatMilitaryInfrastructure:
        stmt = select(NatMilitaryInfrastructure).where(NatMilitaryInfrastructure.company_id == company_id)
        if for_update:
            stmt = stmt.with_for_update()
        row = await session.scalar(stmt)
        if row is None:
            row = NatMilitaryInfrastructure(company_id=company_id)
            session.add(row)
            await session.flush()
        return row

    @staticmethod
    def _field(facility: str) -> str:
        if facility not in FACILITIES:
            raise ValueError("Неизвестный военный объект")
        return f"{facility}_level"

    @classmethod
    def upgrade_quote(cls, infrastructure: NatMilitaryInfrastructure, facility: str) -> dict[str, Any]:
        spec = FACILITIES.get(facility)
        if spec is None:
            raise ValueError("Неизвестный военный объект")
        current = int(getattr(infrastructure, cls._field(facility)))
        if current >= 10:
            raise ValueError("Достигнут максимальный уровень объекта")
        target = current + 1
        factor = 1.62 ** current
        return {
            "facility": facility, "name": spec["name"], "current_level": current,
            "target_level": target, "cash": round(float(spec["base_cash"]) * factor, 2),
            "items": {item: round(float(qty) * (1.35 ** current), 2) for item, qty in spec["items"].items()},
        }

    @staticmethod
    async def _inventory_rows(session: AsyncSession, company_id: int, item_ids) -> dict[str, NatInventory]:
        if not item_ids:
            return {}
        rows = (await session.execute(
            select(NatInventory).where(
                NatInventory.company_id == company_id, NatInventory.item_id.in_(tuple(item_ids))
            ).with_for_update()
        )).scalars().all()
        return {row.item_id: row for row in rows}

    @classmethod
    async def upgrade(cls, session: AsyncSession, company_id: int, facility: str) -> dict[str, Any]:
        company = await session.scalar(select(NatCompany).where(NatCompany.id == company_id).with_for_update())
        if company is None:
            raise ValueError("Компания не найдена")
        infrastructure = await cls.ensure(session, company_id, for_update=True)
        quote = cls.upgrade_quote(infrastructure, facility)
        if float(company.cash) < quote["cash"]:
            raise ValueError("Недостаточно cash для модернизации")
        inventory = await cls._inventory_rows(session, company_id, quote["items"])
        for item_id, quantity in quote["items"].items():
            row = inventory.get(item_id)
            if row is None or float(row.available_quantity) + 1e-9 < quantity:
                raise ValueError(f"Недостаточно ресурса «{get_item_name(item_id)}»: нужно {quantity:g}")
        company.cash = round(float(company.cash) - quote["cash"], 2)
        for item_id, quantity in quote["items"].items():
            inventory[item_id].quantity = round(float(inventory[item_id].quantity) - quantity, 6)
        setattr(infrastructure, cls._field(facility), quote["target_level"])
        await EconomyMetricsService.record(
            session, company_id=company_id, flow="SINK", category="military_infrastructure",
            cash_amount=quote["cash"], context={"facility": facility, "level": quote["target_level"]},
        )
        return {"success": True, **quote, "remaining_cash": company.cash}

    @classmethod
    async def queue_training(
        cls, session: AsyncSession, company: NatCompany, unit_type: str, count: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        ArmyService._validate_count(count)
        recruit = RECRUITMENT_CATALOG.get(unit_type)
        if recruit is None:
            raise ValueError("Неизвестный тип войск")
        locked = await session.scalar(select(NatCompany).where(NatCompany.id == company.id).with_for_update())
        if locked is None:
            raise ValueError("Компания не найдена")
        infrastructure = await cls.ensure(session, company.id, for_update=True)
        facility, required_level = UNIT_REQUIREMENTS[unit_type]
        if int(getattr(infrastructure, cls._field(facility))) < required_level:
            raise ValueError(f"Сначала улучшите «{FACILITIES[facility]['name']}» до ур. {required_level}")
        cash_cost = round(float(recruit["cash_cost"]) * count, 2)
        if float(locked.cash) < cash_cost:
            raise ValueError("Недостаточно cash для подготовки войск")
        item_costs = {item: float(per_unit) * count for item, per_unit in recruit["items"].items()}
        inventory = await cls._inventory_rows(session, company.id, item_costs)
        for item_id, quantity in item_costs.items():
            row = inventory.get(item_id)
            if row is None or float(row.available_quantity) + 1e-9 < quantity:
                raise ValueError(f"Недостаточно ресурса «{get_item_name(item_id)}»: нужно {quantity:g}")
        locked.cash = round(float(locked.cash) - cash_cost, 2)
        for item_id, quantity in item_costs.items():
            inventory[item_id].quantity = round(float(inventory[item_id].quantity) - quantity, 6)
        command_level = int(infrastructure.command_center_level)
        facility_level = int(getattr(infrastructure, cls._field(facility)))
        speed = 1.0 + command_level * 0.06 + facility_level * 0.10
        duration_minutes = max(1, round(BASE_TRAIN_MINUTES[unit_type] * pow(count, 0.72) / speed))
        current = normalize_dt(now or get_game_now())
        training = NatArmyTraining(
            company_id=company.id, unit_type=unit_type, quantity=count,
            started_at=current, ready_at=current + timedelta(minutes=duration_minutes), status="TRAINING",
        )
        session.add(training)
        await session.flush()
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="SINK", category="army_training",
            cash_amount=cash_cost, item_id=unit_type, quantity=count,
        )
        return {
            "success": True, "training_id": training.id, "unit_type": unit_type,
            "quantity": count, "ready_at": training.ready_at, "duration_minutes": duration_minutes,
            "remaining_cash": locked.cash,
        }

    @classmethod
    async def settle_training(cls, session: AsyncSession, company_id: int, *, now: datetime | None = None) -> list[int]:
        current = normalize_dt(now or get_game_now())
        rows = list((await session.execute(
            select(NatArmyTraining).where(
                NatArmyTraining.company_id == company_id,
                NatArmyTraining.status == "TRAINING",
                NatArmyTraining.ready_at <= current,
            ).with_for_update()
        )).scalars().all())
        completed: list[int] = []
        for training in rows:
            unit = await session.scalar(select(NatArmyUnit).where(
                NatArmyUnit.company_id == company_id, NatArmyUnit.unit_type == training.unit_type
            ).with_for_update())
            if unit is None:
                unit = NatArmyUnit(
                    company_id=company_id, unit_type=training.unit_type, quantity=0,
                    level=1, readiness=10_000, experience=0, updated_at=current,
                )
                session.add(unit)
            unit.quantity += int(training.quantity)
            unit.readiness = max(int(unit.readiness), 8_500)
            unit.updated_at = current
            training.status = "COMPLETED"
            completed.append(training.id)
        if completed:
            await session.flush()
            await ArmyService._sync_legacy(session, company_id)
        return completed

    @classmethod
    async def recover_readiness(cls, session: AsyncSession, company_id: int, *, now: datetime | None = None) -> None:
        current = normalize_dt(now or get_game_now())
        infrastructure = await cls.ensure(session, company_id)
        rows = list((await session.execute(
            select(NatArmyUnit).where(NatArmyUnit.company_id == company_id).with_for_update()
        )).scalars().all())
        rate_per_hour = 260 + int(infrastructure.logistics_level) * 35
        for unit in rows:
            updated = normalize_dt(unit.updated_at)
            if updated is None or current <= updated or int(unit.readiness) >= 10_000:
                continue
            hours = min(72.0, (current - updated).total_seconds() / 3600)
            unit.readiness = min(10_000, int(unit.readiness) + round(rate_per_hour * hours))
            unit.updated_at = current

    @classmethod
    async def operation_supply_quote(cls, session: AsyncSession, company_id: int, army: ArmySnapshot) -> dict[str, float]:
        infrastructure = await cls.ensure(session, company_id)
        units = army.units
        logistics_discount = min(0.40, int(infrastructure.logistics_level) * 0.04)
        factor = 1.0 - logistics_discount
        food = (units.get("infantry", 0) * 0.035 + units.get("border_guards", 0) * 0.045 + units.get("tanks", 0) * 0.01) * factor
        fuel = (units.get("tanks", 0) * 0.10 + units.get("drones", 0) * 0.025 + units.get("aircraft", 0) * 0.55 + units.get("air_defense", 0) * 0.05) * factor
        gear = (units.get("infantry", 0) * 0.018 + units.get("border_guards", 0) * 0.03 + units.get("tanks", 0) * 0.005) * factor
        return {"food": round(food, 2), "fuel_diesel": round(fuel, 2), "military_gear": round(gear, 2)}

    @classmethod
    async def consume_operation_supply(cls, session: AsyncSession, company_id: int, army: ArmySnapshot) -> dict[str, float]:
        quote = {k: v for k, v in (await cls.operation_supply_quote(session, company_id, army)).items() if v > 0}
        inventory = await cls._inventory_rows(session, company_id, quote)
        missing = []
        for item_id, quantity in quote.items():
            row = inventory.get(item_id)
            available = float(row.available_quantity) if row else 0.0
            if available + 1e-9 < quantity:
                label = CANONICAL_ITEMS.get(item_id, {}).get("name", "Ресурс снабжения")
                missing.append(f"{label}: {available:g}/{quantity:g}")
        if missing:
            raise ValueError("Недостаточно армейского снабжения: " + ", ".join(missing))
        for item_id, quantity in quote.items():
            inventory[item_id].quantity = round(float(inventory[item_id].quantity) - quantity, 6)
        return quote

    @classmethod
    async def reduce_readiness_after_operation(cls, session: AsyncSession, company_id: int, *, loss_ratio: float = 0.0) -> None:
        penalty = min(4_000, round(900 + max(0.0, loss_ratio) * 4_000))
        rows = list((await session.execute(
            select(NatArmyUnit).where(NatArmyUnit.company_id == company_id).with_for_update()
        )).scalars().all())
        current = normalize_dt(get_game_now())
        for unit in rows:
            unit.readiness = max(2_500, int(unit.readiness) - penalty)
            unit.updated_at = current

    @classmethod
    async def status(cls, session: AsyncSession, company_id: int, *, now: datetime | None = None) -> dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        completed = await cls.settle_training(session, company_id, now=current)
        await cls.recover_readiness(session, company_id, now=current)
        infrastructure = await cls.ensure(session, company_id)
        queue = list((await session.execute(
            select(NatArmyTraining).where(
                NatArmyTraining.company_id == company_id, NatArmyTraining.status == "TRAINING"
            ).order_by(NatArmyTraining.ready_at)
        )).scalars().all())
        levels = {facility: int(getattr(infrastructure, cls._field(facility))) for facility in FACILITIES}
        quotes = {}
        for facility in FACILITIES:
            try:
                quotes[facility] = cls.upgrade_quote(infrastructure, facility)
            except ValueError:
                quotes[facility] = None
        return {
            "levels": levels, "upgrade_quotes": quotes, "completed_training_ids": completed,
            "training_queue": [{"id": row.id, "unit_type": row.unit_type, "quantity": row.quantity, "ready_at": row.ready_at} for row in queue],
        }


__all__ = ["FACILITIES", "MilitaryInfrastructureService"]
