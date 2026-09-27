"""Transactional hospital admission, unit treatment and equipment repair."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import game_dt_iso, get_game_now, normalize_dt
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.hospital import NatHospitalWard
from backend.natbirzha.models.inventory import NatInventory, get_item_name
from backend.natbirzha.models.military_infrastructure import NatMilitaryInfrastructure
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.hospital_rules import (
    HOSPITAL_BEDS_PER_LEVEL,
    HUMAN_UNITS,
    MAX_HOSPITAL_LEVEL,
    MAX_REPAIR_DEPOT_LEVEL,
    REPAIR_BAYS_PER_LEVEL,
    REPAIR_MATERIALS_PER_UNIT,
    REPAIR_UNITS,
    TREATMENT_CASH_PER_UNIT,
    allocate_capacity,
    classify_losses,
    hospital_capacity,
    repair_depot_capacity,
    treatment_duration_minutes,
)
from backend.natbirzha.services.military_infrastructure_service import MilitaryInfrastructureService
from backend.natbirzha.services.unit_catalog import UNIT_CATALOG


class HospitalService:
    @staticmethod
    async def _lock_company(session: AsyncSession, company_id: int) -> NatCompany:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Компания не найдена")
        return company

    @staticmethod
    async def _wards(
        session: AsyncSession, company_id: int, *, for_update: bool = False
    ) -> list[NatHospitalWard]:
        statement = (
            select(NatHospitalWard)
            .where(NatHospitalWard.company_id == company_id)
            .order_by(NatHospitalWard.unit_type)
        )
        if for_update:
            statement = statement.with_for_update()
        return list((await session.execute(statement)).scalars().all())

    @classmethod
    async def _ward(
        cls, session: AsyncSession, company_id: int, unit_type: str
    ) -> NatHospitalWard:
        row = await session.scalar(
            select(NatHospitalWard).where(
                NatHospitalWard.company_id == company_id,
                NatHospitalWard.unit_type == unit_type,
            ).with_for_update()
        )
        if row is None:
            row = NatHospitalWard(
                company_id=company_id, unit_type=unit_type,
                wounded_count=0, healing_count=0,
            )
            session.add(row)
            await session.flush()
        return row

    @staticmethod
    def classify_losses(losses: Mapping[str, int], *, mode: str) -> dict[str, dict[str, int]]:
        return classify_losses(losses, mode)

    @staticmethod
    def _positive(values: Mapping[str, int]) -> dict[str, int]:
        return {key: int(value) for key, value in values.items() if int(value) > 0}

    @staticmethod
    async def army_counts(session: AsyncSession, company_id: int) -> dict[str, int]:
        snapshot = await ArmyService.snapshot(session, company_id)
        return {unit_type: int(snapshot.units.get(unit_type, 0)) for unit_type in UNIT_CATALOG}

    @classmethod
    async def apply_combat_losses(
        cls,
        session: AsyncSession,
        company_id: int,
        losses: Mapping[str, int],
        *,
        mode: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Move severe casualties into available beds/bays and permanently remove overflow."""
        current = normalize_dt(now or get_game_now())
        await cls._lock_company(session, company_id)
        infrastructure = await MilitaryInfrastructureService.ensure(
            session, company_id, for_update=True
        )
        wards = await cls._wards(session, company_id, for_update=True)
        occupied_hospital = sum(
            int(row.wounded_count) + int(row.healing_count)
            for row in wards if row.unit_type in HUMAN_UNITS
        )
        occupied_repair = sum(
            int(row.wounded_count) + int(row.healing_count)
            for row in wards if row.unit_type in REPAIR_UNITS
        )
        free_hospital = max(
            0, hospital_capacity(infrastructure.hospital_level) - occupied_hospital
        )
        free_repair = max(
            0, repair_depot_capacity(infrastructure.repair_depot_level) - occupied_repair
        )

        split = classify_losses(losses, mode)
        severe = split["severe_wounded"]
        human_severe = {key: value for key, value in severe.items() if key in HUMAN_UNITS}
        repair_severe = {key: value for key, value in severe.items() if key in REPAIR_UNITS}
        admitted = {
            **allocate_capacity(human_severe, free_hospital),
            **allocate_capacity(repair_severe, free_repair),
        }
        fatalities = dict(split["fatalities"])
        for unit_type, count in severe.items():
            overflow = int(count) - int(admitted.get(unit_type, 0))
            if overflow > 0:
                fatalities[unit_type] = int(fatalities.get(unit_type, 0)) + overflow

        for unit_type, count in admitted.items():
            if count <= 0:
                continue
            ward = next((row for row in wards if row.unit_type == unit_type), None)
            if ward is None:
                ward = NatHospitalWard(
                    company_id=company_id, unit_type=unit_type,
                    wounded_count=0, healing_count=0,
                )
                session.add(ward)
            ward.wounded_count += int(count)
            ward.updated_at = current

        removed = {
            unit_type: int(severe.get(unit_type, 0)) + int(split["fatalities"].get(unit_type, 0))
            for unit_type in set(severe) | set(split["fatalities"])
        }
        if any(removed.values()):
            await ArmyService.apply_losses(session, company_id, removed)
        snapshot = await ArmyService.snapshot(session, company_id)
        remaining = {unit_type: int(quantity) for unit_type, quantity in snapshot.units.items()}
        return {
            "mode": str(mode).upper(),
            "raw_losses": cls._positive(losses),
            "light_wounded": cls._positive(split["light_wounded"]),
            "hospitalized": cls._positive(admitted),
            "fatalities": cls._positive(fatalities),
            "remaining": remaining,
        }

    @classmethod
    async def _return_to_army(
        cls, session: AsyncSession, company_id: int, unit_type: str, count: int, now: datetime
    ) -> None:
        row = await session.scalar(
            select(NatArmyUnit).where(
                NatArmyUnit.company_id == company_id,
                NatArmyUnit.unit_type == unit_type,
            ).with_for_update()
        )
        if row is None:
            row = NatArmyUnit(
                company_id=company_id,
                unit_type=unit_type,
                quantity=0,
                level=1,
                readiness=8_500,
                experience=0,
                updated_at=now,
            )
            session.add(row)
        row.quantity += int(count)
        row.readiness = max(int(row.readiness), 8_500)
        row.updated_at = now

    @classmethod
    async def collect_treated(
        cls,
        session: AsyncSession,
        company_id: int,
        *,
        unit_type: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, int]:
        current = normalize_dt(now or get_game_now())
        await cls._lock_company(session, company_id)
        wards = await cls._wards(session, company_id, for_update=True)
        collected: dict[str, int] = {}
        for ward in wards:
            if unit_type and ward.unit_type != unit_type:
                continue
            ready_at = normalize_dt(ward.healing_ready_at)
            count = int(ward.healing_count)
            if count <= 0 or ready_at is None or ready_at > current:
                continue
            await cls._return_to_army(session, company_id, ward.unit_type, count, current)
            collected[ward.unit_type] = count
            ward.healing_count = 0
            ward.healing_started_at = None
            ward.healing_ready_at = None
            ward.updated_at = current
        if collected:
            await session.flush()
            await ArmyService._sync_legacy(session, company_id)
        return collected

    @classmethod
    async def _inventory_rows(
        cls, session: AsyncSession, company_id: int, item_ids: Mapping[str, float]
    ) -> dict[str, NatInventory]:
        if not item_ids:
            return {}
        rows = (await session.execute(
            select(NatInventory)
            .where(
                NatInventory.company_id == company_id,
                NatInventory.item_id.in_(tuple(item_ids)),
            )
            .order_by(NatInventory.item_id)
            .with_for_update()
        )).scalars().all()
        return {row.item_id: row for row in rows}

    @classmethod
    async def start_treatment(
        cls,
        session: AsyncSession,
        company_id: int,
        unit_type: str,
        count: int,
        *,
        instant: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        if unit_type not in UNIT_CATALOG:
            raise ValueError("Неизвестный тип войск")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("Количество должно быть положительным целым числом")
        if unit_type not in HUMAN_UNITS | REPAIR_UNITS:
            raise ValueError("Этот тип войск нельзя лечить или ремонтировать")
        company = await cls._lock_company(session, company_id)
        ward = await cls._ward(session, company_id, unit_type)
        if int(ward.healing_count) > 0:
            raise ValueError("Сначала заберите завершённую партию этого подразделения")
        if count > int(ward.wounded_count):
            raise ValueError("В госпитале нет столько раненых")

        base_cash = float(TREATMENT_CASH_PER_UNIT[unit_type]) * count
        cash_paid = round(base_cash * (1.5 if instant else 1.0), 2)
        materials = {
            item: round(float(per_unit) * count, 6)
            for item, per_unit in REPAIR_MATERIALS_PER_UNIT[unit_type].items()
        }
        if float(company.cash) + 1e-9 < cash_paid:
            raise ValueError("Недостаточно cash для лечения или ремонта")
        inventory = await cls._inventory_rows(session, company_id, materials)
        for item_id, quantity in materials.items():
            row = inventory.get(item_id)
            available = float(row.available_quantity) if row else 0.0
            if available + 1e-9 < quantity:
                raise ValueError(
                    f"Недостаточно ресурса «{get_item_name(item_id)}»: "
                    f"нужно {quantity:g}, доступно {available:g}"
                )

        company.cash = round(float(company.cash) - cash_paid, 2)
        for item_id, quantity in materials.items():
            inventory[item_id].quantity = max(
                0.0, round(float(inventory[item_id].quantity) - quantity, 6)
            )
        ward.wounded_count -= count
        ward.updated_at = current
        duration = 0 if instant else treatment_duration_minutes(unit_type, count)
        if instant:
            await cls._return_to_army(session, company_id, unit_type, count, current)
            await session.flush()
            await ArmyService._sync_legacy(session, company_id)
        else:
            ward.healing_count = count
            ward.healing_started_at = current
            ward.healing_ready_at = current + timedelta(minutes=duration)

        await EconomyMetricsService.record(
            session,
            company_id=company_id,
            flow="SINK",
            category="military_hospital" if unit_type in HUMAN_UNITS else "military_repair",
            cash_amount=cash_paid,
            context={"unit_type": unit_type, "quantity": count, "instant": instant},
        )
        return {
            "success": True,
            "unit_type": unit_type,
            "quantity": count,
            "instant": instant,
            "cash_paid": cash_paid,
            "materials_paid": materials,
            "duration_minutes": duration,
            "ready_at": game_dt_iso(ward.healing_ready_at) if ward.healing_ready_at else None,
            "remaining_cash": company.cash,
        }

    @classmethod
    async def start_all_treatments(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        await cls.collect_treated(session, company_id, now=current)
        wards = await cls._wards(session, company_id, for_update=True)
        started: dict[str, dict[str, Any]] = {}
        skipped: dict[str, str] = {}
        for ward in wards:
            quantity = int(ward.wounded_count)
            if quantity <= 0:
                continue
            try:
                result = await cls.start_treatment(
                    session, company_id, ward.unit_type, quantity, now=current
                )
                started[ward.unit_type] = result
            except ValueError as exc:
                skipped[ward.unit_type] = str(exc)
        return {"started": started, "skipped": skipped}

    @classmethod
    async def get_status(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None
    ) -> dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        infrastructure = await MilitaryInfrastructureService.ensure(session, company_id)
        wards = await cls._wards(session, company_id)
        hospital_wards = [row for row in wards if row.unit_type in HUMAN_UNITS]
        repair_wards = [row for row in wards if row.unit_type in REPAIR_UNITS]

        def facility(level: int, max_level: int, capacity: int, rows: list[NatHospitalWard]):
            occupied = sum(int(row.wounded_count) + int(row.healing_count) for row in rows)
            return {
                "level": int(level),
                "max_level": max_level,
                "capacity": capacity,
                "occupied": occupied,
                "available": max(0, capacity - occupied),
                "wards": [{
                    "unit_type": row.unit_type,
                    "wounded_count": int(row.wounded_count),
                    "healing_count": int(row.healing_count),
                    "healing_started_at": game_dt_iso(row.healing_started_at) if row.healing_started_at else None,
                    "healing_ready_at": game_dt_iso(row.healing_ready_at) if row.healing_ready_at else None,
                    "ready": bool(
                        int(row.healing_count) > 0
                        and normalize_dt(row.healing_ready_at) is not None
                        and normalize_dt(row.healing_ready_at) <= current
                    ),
                } for row in rows if int(row.wounded_count) > 0 or int(row.healing_count) > 0],
            }

        return {
            "hospital": facility(
                infrastructure.hospital_level, MAX_HOSPITAL_LEVEL,
                hospital_capacity(infrastructure.hospital_level), hospital_wards,
            ),
            "repair_depot": facility(
                infrastructure.repair_depot_level, MAX_REPAIR_DEPOT_LEVEL,
                repair_depot_capacity(infrastructure.repair_depot_level), repair_wards,
            ),
        }


__all__ = ["HospitalService"]