"""Playable fleet, workforce and internal project loops for V2 businesses."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.business_assets import NatBusinessEmployee, NatBusinessProject, NatBusinessVehicle
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory, get_item_name
from backend.natbirzha.services.business_asset_catalog import EMPLOYEE_CATALOG, PROJECT_CATALOG, VEHICLE_CATALOG
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


class BusinessAssetService:
    @staticmethod
    def vehicle_slots(stage: int) -> int:
        return min(8, 1 + max(0, int(stage) - 1) // 10)

    @staticmethod
    def employee_slots(stage: int) -> int:
        return min(10, 2 + max(0, int(stage) - 1) // 8)

    @staticmethod
    def project_slots(stage: int) -> int:
        return min(3, 1 + max(0, int(stage) - 1) // 20)

    @staticmethod
    async def _business(session: AsyncSession, company_id: int, business_id: int) -> NatBusiness:
        row = await session.scalar(
            select(NatBusiness).where(
                NatBusiness.id == business_id, NatBusiness.company_id == company_id
            ).with_for_update()
        )
        if row is None:
            raise ValueError("Предприятие не найдено")
        return row

    @staticmethod
    async def _company(session: AsyncSession, company_id: int) -> NatCompany:
        row = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if row is None:
            raise ValueError("Компания не найдена")
        return row

    @classmethod
    async def _refresh_modifiers(cls, session: AsyncSession, business: NatBusiness) -> None:
        vehicles = list((await session.execute(
            select(NatBusinessVehicle).where(NatBusinessVehicle.business_id == business.id)
        )).scalars().all())
        employees = list((await session.execute(
            select(NatBusinessEmployee).where(
                NatBusinessEmployee.business_id == business.id,
                NatBusinessEmployee.status == "ACTIVE",
            )
        )).scalars().all())
        fleet_bonus = sum(
            float(VEHICLE_CATALOG.get(v.vehicle_type, {}).get("output_bonus", 0.0))
            * min(1.0, max(0.0, float(v.condition) / max(1.0, float(v.max_condition))))
            for v in vehicles
        )
        workforce_bonus = sum(
            float(EMPLOYEE_CATALOG.get(e.role, {}).get("output_bonus", 0.0)) * max(0.5, float(e.quality))
            for e in employees
        )
        salary = sum(float(e.salary_per_hour) for e in employees)
        vehicle_maintenance = sum(
            float(VEHICLE_CATALOG.get(v.vehicle_type, {}).get("maintenance_per_hour", 0.0))
            for v in vehicles
        )
        metadata = dict(business.metadata_json or {})
        project_bonus = min(0.35, max(0.0, float(metadata.get("project_output_bonus", 0.0) or 0.0)))
        metadata["asset_output_multiplier"] = round(1.0 + min(0.35, fleet_bonus) + min(0.30, workforce_bonus) + project_bonus, 6)
        metadata["asset_salary_per_hour"] = round(salary, 2)
        metadata["asset_maintenance_per_hour"] = round(vehicle_maintenance, 2)
        business.metadata_json = metadata

    @classmethod
    async def purchase_vehicle(cls, session: AsyncSession, company_id: int, business_id: int, vehicle_type: str) -> dict[str, Any]:
        spec = VEHICLE_CATALOG.get(vehicle_type)
        if spec is None:
            raise ValueError("Неизвестный тип транспорта")
        business = await cls._business(session, company_id, business_id)
        if business.specialization != "logistics":
            raise ValueError("Автопарк доступен только логистическим предприятиям")
        if int(business.stage) < int(spec["min_business_stage"]):
            raise ValueError(f"Транспорт откроется на уровне предприятия {spec['min_business_stage']}")
        rows = list((await session.execute(
            select(NatBusinessVehicle).where(NatBusinessVehicle.business_id == business.id)
        )).scalars().all())
        if len(rows) >= cls.vehicle_slots(business.stage):
            raise ValueError("Все места автопарка заняты")
        company = await cls._company(session, company_id)
        cost = float(spec["cost"])
        if float(company.cash) < cost:
            raise ValueError("Недостаточно cash для покупки транспорта")
        company.cash = round(float(company.cash) - cost, 2)
        vehicle = NatBusinessVehicle(
            business_id=business.id, vehicle_type=vehicle_type, vehicle_tier=int(spec["tier"]),
            condition=100.0, max_condition=100.0, purchase_price=cost,
            income_per_hour=0.0, wear_per_hour=float(spec["wear_per_hour"]),
        )
        session.add(vehicle)
        await session.flush()
        await cls._refresh_modifiers(session, business)
        await EconomyMetricsService.record(session, company_id=company.id, flow="SINK", category="fleet_purchase", cash_amount=cost)
        return {"success": True, "vehicle_id": vehicle.id, "remaining_cash": company.cash}

    @classmethod
    async def repair_vehicle(cls, session: AsyncSession, company_id: int, vehicle_id: int) -> dict[str, Any]:
        vehicle = await session.scalar(
            select(NatBusinessVehicle).join(NatBusiness).where(
                NatBusinessVehicle.id == vehicle_id, NatBusiness.company_id == company_id
            ).with_for_update()
        )
        if vehicle is None:
            raise ValueError("Транспорт не найден")
        company = await cls._company(session, company_id)
        missing = max(0.0, float(vehicle.max_condition) - float(vehicle.condition))
        repair_cost = round(float(vehicle.purchase_price) * 0.006 * missing, 2)
        if float(company.cash) < repair_cost:
            raise ValueError("Недостаточно cash для ремонта")
        company.cash = round(float(company.cash) - repair_cost, 2)
        vehicle.condition = float(vehicle.max_condition)
        business = await session.get(NatBusiness, vehicle.business_id)
        if business is not None:
            await cls._refresh_modifiers(session, business)
        return {"success": True, "vehicle_id": vehicle.id, "repair_cost": repair_cost, "remaining_cash": company.cash}

    @classmethod
    async def hire_employee(cls, session: AsyncSession, company_id: int, business_id: int, role: str) -> dict[str, Any]:
        spec = EMPLOYEE_CATALOG.get(role)
        if spec is None:
            raise ValueError("Неизвестная должность")
        business = await cls._business(session, company_id, business_id)
        if business.specialization not in spec["specializations"]:
            raise ValueError("Эта должность не подходит выбранному предприятию")
        if int(business.stage) < int(spec["min_business_stage"]):
            raise ValueError(f"Должность откроется на уровне предприятия {spec['min_business_stage']}")
        count = await session.scalar(
            select(func.count(NatBusinessEmployee.id)).where(
                NatBusinessEmployee.business_id == business.id, NatBusinessEmployee.status == "ACTIVE"
            )
        )
        if int(count or 0) >= cls.employee_slots(business.stage):
            raise ValueError("Все штатные места заняты")
        company = await cls._company(session, company_id)
        cost = float(spec["hire_cost"])
        if float(company.cash) < cost:
            raise ValueError("Недостаточно cash для найма")
        company.cash = round(float(company.cash) - cost, 2)
        employee = NatBusinessEmployee(
            business_id=business.id, role=role, skill=1,
            salary_per_hour=float(spec["salary_per_hour"]), quality=float(spec["quality"]), status="ACTIVE",
        )
        session.add(employee)
        await session.flush()
        await cls._refresh_modifiers(session, business)
        return {"success": True, "employee_id": employee.id, "remaining_cash": company.cash}

    @classmethod
    async def fire_employee(cls, session: AsyncSession, company_id: int, employee_id: int) -> dict[str, Any]:
        employee = await session.scalar(
            select(NatBusinessEmployee).join(NatBusiness).where(
                NatBusinessEmployee.id == employee_id, NatBusiness.company_id == company_id
            ).with_for_update()
        )
        if employee is None:
            raise ValueError("Сотрудник не найден")
        employee.status = "FIRED"
        business = await session.get(NatBusiness, employee.business_id)
        if business is not None:
            await cls._refresh_modifiers(session, business)
        return {"success": True, "employee_id": employee.id}

    @classmethod
    async def start_project(cls, session: AsyncSession, company_id: int, business_id: int, project_type: str, *, now: datetime | None = None) -> dict[str, Any]:
        spec = PROJECT_CATALOG.get(project_type)
        if spec is None:
            raise ValueError("Неизвестный проект")
        business = await cls._business(session, company_id, business_id)
        if business.specialization not in spec["specializations"] or int(business.stage) < int(spec["min_stage"]):
            raise ValueError("Проект пока недоступен этому предприятию")
        active = list((await session.execute(
            select(NatBusinessProject).where(NatBusinessProject.business_id == business.id, NatBusinessProject.status == "ACTIVE")
        )).scalars().all())
        if len(active) >= cls.project_slots(business.stage):
            raise ValueError("Все проектные мощности заняты")
        company = await cls._company(session, company_id)
        if float(company.cash) < float(spec["cost_cash"]):
            raise ValueError("Недостаточно cash для запуска проекта")
        inventories = {row.item_id: row for row in (await session.execute(
            select(NatInventory).where(NatInventory.company_id == company.id, NatInventory.item_id.in_(tuple(spec["inputs"]))).with_for_update()
        )).scalars().all()}
        for item_id, quantity in spec["inputs"].items():
            row = inventories.get(item_id)
            if row is None or float(row.available_quantity) + 1e-9 < float(quantity):
                raise ValueError(f"Недостаточно ресурса «{get_item_name(item_id)}»: нужно {quantity:g}")
        company.cash = round(float(company.cash) - float(spec["cost_cash"]), 2)
        for item_id, quantity in spec["inputs"].items():
            inventories[item_id].quantity = round(float(inventories[item_id].quantity) - float(quantity), 6)
        current = normalize_dt(now or get_game_now())
        project = NatBusinessProject(
            business_id=business.id, project_type=project_type, status="ACTIVE",
            started_at=current, ready_at=current + timedelta(hours=float(spec["duration_hours"])),
            reward_cash=float(spec["reward_cash"]), cost_cash=float(spec["cost_cash"]),
            input_snapshot_json=dict(spec["inputs"]), result_snapshot_json={"permanent_output_bonus": spec["permanent_output_bonus"]},
        )
        session.add(project)
        await session.flush()
        return {"success": True, "project_id": project.id, "ready_at": project.ready_at, "remaining_cash": company.cash}

    @classmethod
    async def settle_due_projects(cls, session: AsyncSession, company: NatCompany, *, now: datetime | None = None) -> list[int]:
        current = normalize_dt(now or get_game_now())
        rows = list((await session.execute(
            select(NatBusinessProject).join(NatBusiness).where(
                NatBusiness.company_id == company.id, NatBusinessProject.status == "ACTIVE", NatBusinessProject.ready_at <= current
            ).with_for_update()
        )).scalars().all())
        completed: list[int] = []
        for project in rows:
            project.status = "COMPLETED"
            company.cash = round(float(company.cash) + float(project.reward_cash or 0.0), 2)
            business = await session.get(NatBusiness, project.business_id)
            if business is not None:
                metadata = dict(business.metadata_json or {})
                bonus = float((project.result_snapshot_json or {}).get("permanent_output_bonus", 0.0))
                metadata["project_output_bonus"] = round(min(0.35, float(metadata.get("project_output_bonus", 0.0)) + bonus), 6)
                business.metadata_json = metadata
                await cls._refresh_modifiers(session, business)
            completed.append(project.id)
        return completed

    @classmethod
    async def apply_vehicle_wear(cls, session: AsyncSession, business: NatBusiness, worked_hours: float) -> None:
        if worked_hours <= 0 or business.specialization != "logistics":
            return
        rows = list((await session.execute(
            select(NatBusinessVehicle).where(NatBusinessVehicle.business_id == business.id).with_for_update()
        )).scalars().all())
        changed = False
        for vehicle in rows:
            before = float(vehicle.condition)
            vehicle.condition = round(max(0.0, before - float(vehicle.wear_per_hour) * worked_hours), 3)
            changed = changed or abs(before - vehicle.condition) > 1e-9
        if changed:
            await cls._refresh_modifiers(session, business)

    @classmethod
    async def snapshot_for_businesses(cls, session: AsyncSession, businesses: list[NatBusiness]) -> dict[int, dict[str, Any]]:
        if not businesses:
            return {}
        ids = [row.id for row in businesses]
        vehicles = list((await session.execute(select(NatBusinessVehicle).where(NatBusinessVehicle.business_id.in_(ids)))).scalars().all())
        employees = list((await session.execute(select(NatBusinessEmployee).where(NatBusinessEmployee.business_id.in_(ids), NatBusinessEmployee.status == "ACTIVE"))).scalars().all())
        projects = list((await session.execute(select(NatBusinessProject).where(NatBusinessProject.business_id.in_(ids)).order_by(NatBusinessProject.started_at.desc()))).scalars().all())
        result: dict[int, dict[str, Any]] = {}
        for business in businesses:
            bvehicles = [v for v in vehicles if v.business_id == business.id]
            bemployees = [e for e in employees if e.business_id == business.id]
            bprojects = [p for p in projects if p.business_id == business.id][:8]
            result[business.id] = {
                "vehicles": [{"id": v.id, "type": v.vehicle_type, "name": VEHICLE_CATALOG.get(v.vehicle_type, {}).get("name", v.vehicle_type), "icon": VEHICLE_CATALOG.get(v.vehicle_type, {}).get("icon", "🚚"), "condition": round(float(v.condition), 1)} for v in bvehicles],
                "vehicle_slots": {"used": len(bvehicles), "max": cls.vehicle_slots(business.stage)},
                "employees": [{"id": e.id, "role": e.role, "name": EMPLOYEE_CATALOG.get(e.role, {}).get("name", e.role), "icon": EMPLOYEE_CATALOG.get(e.role, {}).get("icon", "👤"), "salary_per_hour": e.salary_per_hour} for e in bemployees],
                "employee_slots": {"used": len(bemployees), "max": cls.employee_slots(business.stage)},
                "projects": [{"id": p.id, "type": p.project_type, "name": PROJECT_CATALOG.get(p.project_type, {}).get("name", p.project_type), "status": p.status, "ready_at": p.ready_at, "reward_cash": p.reward_cash} for p in bprojects],
                "project_slots": {"used": sum(p.status == "ACTIVE" for p in bprojects), "max": cls.project_slots(business.stage)},
            }
        return result


__all__ = ["BusinessAssetService"]
