"""Transactional normalized army recruitment and casualty handling."""

from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.military import NatArmy
from backend.natbirzha.services.combat_resolver import ArmySnapshot
from backend.natbirzha.services.unit_catalog import UNIT_CATALOG
from backend.natbirzha.services.mastery_service import MasteryService
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


RECRUITMENT_CATALOG: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        "infantry": {"cash_cost": 50.0, "items": {}},
        "border_guards": {"cash_cost": 100.0, "items": {"military_gear": 0.25}},
        "tanks": {"cash_cost": 1000.0, "items": {"steel": 1.0}},
        "drones": {"cash_cost": 500.0, "items": {"electronics": 1.0}},
        "aircraft": {
            "cash_cost": 5000.0,
            "items": {
                "aluminum": 2.0, "electronics": 2.0, "jet_fuel": 10.0,
                "advanced_alloy": 0.5, "advanced_composite": 0.5,
                "titanium_alloy": 0.25,
            },
        },
        "air_defense": {
            "cash_cost": 1500.0,
            "items": {"steel": 2.0, "electronics": 1.0},
        },
    }
)


class ArmyService:
    @staticmethod
    def _validate_count(count: int) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("Count must be a positive integer")
        if count > 100_000:
            raise ValueError("Recruitment batch cannot exceed 100000 units")

    @staticmethod
    async def _locked_company(session: AsyncSession, company_id: int) -> NatCompany:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Company not found")
        return company

    @staticmethod
    async def _unit_rows(
        session: AsyncSession, company_id: int, *, for_update: bool = False
    ) -> list[NatArmyUnit]:
        statement = select(NatArmyUnit).where(NatArmyUnit.company_id == company_id)
        if for_update:
            statement = statement.with_for_update()
        return list((await session.execute(statement)).scalars().all())

    @staticmethod
    def _strengths(rows: list[NatArmyUnit]) -> tuple[dict[str, int], int]:
        phases = {"recon": 0, "air": 0, "air_defense": 0, "ground": 0}
        for row in rows:
            spec = UNIT_CATALOG.get(row.unit_type)
            if spec is None:
                # Ignore stale unit codes left by earlier game versions. A
                # legacy row must not make every tournament/API read fail.
                continue
            level_multiplier = 1.0 + min(max(row.level, 0), 20) * 0.03
            readiness_multiplier = min(1.0, max(0.25, row.readiness / 10_000))
            strength = round(row.quantity * spec.base_power * level_multiplier * readiness_multiplier)
            phases[spec.phase] += strength
        return phases, sum(phases.values())

    @classmethod
    async def _sync_legacy(cls, session: AsyncSession, company_id: int) -> NatArmy:
        rows = await cls._unit_rows(session, company_id)
        quantities = {row.unit_type: row.quantity for row in rows}
        _, total_strength = cls._strengths(rows)
        legacy = await session.scalar(
            select(NatArmy).where(NatArmy.company_id == company_id).with_for_update()
        )
        if legacy is None:
            legacy = NatArmy(company_id=company_id)
            session.add(legacy)
        for unit_type in ("infantry", "tanks", "drones", "air_defense"):
            setattr(legacy, unit_type, quantities.get(unit_type, 0))
        legacy.army_strength = total_strength
        legacy.updated_at = datetime.utcnow()
        await session.flush()
        return legacy

    @classmethod
    async def recruit(
        cls,
        session: AsyncSession,
        company: NatCompany,
        unit_type: str,
        count: int,
    ) -> dict[str, Any]:
        cls._validate_count(count)
        spec = RECRUITMENT_CATALOG.get(unit_type)
        if spec is None:
            raise ValueError(f"Unknown unit type: {unit_type}")

        locked_company = await cls._locked_company(session, company.id)
        base_cash = float(spec["cash_cost"]) * count
        total_cash = round(base_cash * (1.0 - MasteryService.effect(locked_company, "doctrine")), 2)
        if locked_company.cash < total_cash:
            raise ValueError(
                f"Insufficient cash. Required: {total_cash}, Available: {locked_company.cash}"
            )

        item_costs: Mapping[str, float] = spec["items"]
        inventory_by_item: dict[str, NatInventory] = {}
        if item_costs:
            rows = (
                await session.execute(
                    select(NatInventory)
                    .where(
                        NatInventory.company_id == company.id,
                        NatInventory.item_id.in_(tuple(item_costs)),
                    )
                    .with_for_update()
                )
            ).scalars().all()
            inventory_by_item = {row.item_id: row for row in rows}
            for item_id, per_unit in item_costs.items():
                required = per_unit * count
                inventory = inventory_by_item.get(item_id)
                available = inventory.available_quantity if inventory else 0.0
                if available < required:
                    raise ValueError(
                        f"Insufficient {item_id}. Required: {required}, Available: {available}"
                    )

        unit_row = await session.scalar(
            select(NatArmyUnit)
            .where(
                NatArmyUnit.company_id == company.id,
                NatArmyUnit.unit_type == unit_type,
            )
            .with_for_update()
        )
        if unit_row is None:
            unit_row = NatArmyUnit(
                company_id=company.id,
                unit_type=unit_type,
                quantity=0,
                level=1,
                readiness=10_000,
                experience=0,
            )
            session.add(unit_row)

        locked_company.cash = round(locked_company.cash - total_cash, 2)
        for item_id, per_unit in item_costs.items():
            inventory_by_item[item_id].quantity -= per_unit * count
        unit_row.quantity += count
        unit_row.updated_at = datetime.utcnow()
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="SINK", category="army_recruitment",
            cash_amount=total_cash, item_id=unit_type, quantity=count,
        )
        await session.flush()
        legacy = await cls._sync_legacy(session, company.id)
        return {
            "success": True,
            "unit_type": unit_type,
            "count_recruited": count,
            "new_quantity": unit_row.quantity,
            "new_army_strength": legacy.army_strength,
            "remaining_cash": locked_company.cash,
            "cash_cost": total_cash,
            "base_cash_cost": base_cash,
        }

    @classmethod
    async def snapshot(
        cls, session: AsyncSession, company_id: int, *, for_update: bool = False
    ) -> ArmySnapshot:
        rows = await cls._unit_rows(session, company_id, for_update=for_update)
        rows = [row for row in rows if row.unit_type in UNIT_CATALOG]
        return ArmySnapshot(
            units={row.unit_type: row.quantity for row in rows},
            levels={row.unit_type: row.level for row in rows},
            readiness={row.unit_type: row.readiness / 10_000 for row in rows},
        )

    @classmethod
    async def apply_losses(
        cls, session: AsyncSession, company_id: int, losses: Mapping[str, int]
    ) -> ArmySnapshot:
        unknown = set(losses) - set(UNIT_CATALOG)
        if unknown:
            raise ValueError(f"Unknown unit losses: {', '.join(sorted(unknown))}")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in losses.values()
        ):
            raise ValueError("Loss quantities must be non-negative integers")

        await cls._locked_company(session, company_id)
        rows = await cls._unit_rows(session, company_id, for_update=True)
        by_type = {row.unit_type: row for row in rows}
        for unit_type, loss in losses.items():
            available = by_type.get(unit_type).quantity if unit_type in by_type else 0
            if loss > available:
                raise ValueError(
                    f"Losses for {unit_type} exceed locked quantity: {loss} > {available}"
                )
        for unit_type, loss in losses.items():
            if unit_type in by_type:
                by_type[unit_type].quantity -= loss
                by_type[unit_type].updated_at = datetime.utcnow()
        await session.flush()
        await cls._sync_legacy(session, company_id)
        return await cls.snapshot(session, company_id)

    @classmethod
    async def compatibility_status(cls, session: AsyncSession, company_id: int) -> dict[str, Any]:
        rows = await cls._unit_rows(session, company_id)
        rows = [row for row in rows if row.unit_type in UNIT_CATALOG]
        quantities = {unit_type: 0 for unit_type in UNIT_CATALOG}
        quantities.update({row.unit_type: row.quantity for row in rows})
        levels = {row.unit_type: row.level for row in rows}
        readiness = {row.unit_type: row.readiness / 10_000 for row in rows}
        phases, total_strength = cls._strengths(rows)
        return {
            "company_id": company_id,
            **quantities,
            "levels": levels,
            "readiness": readiness,
            "phase_strengths": phases,
            "army_strength": total_strength,
        }

