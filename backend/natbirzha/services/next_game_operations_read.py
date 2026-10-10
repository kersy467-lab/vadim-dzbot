"""Concrete quotes and effects for progressive factory management screens."""
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameFacility
from backend.natbirzha.models.next_game_operations import (
    NatNextGameOperations as Operations, NatNextGameFactoryOperations as Factory,
    NatNextGameEmployee as Employee, NatNextGameVehicle as Vehicle,
)
from backend.natbirzha.next_game_catalog import find_next_game_branch, get_next_game_items
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_service.common import _utcnow, facility_recipe_at_level
from backend.natbirzha.services.next_game_operations_catalog import (
    EMPLOYEES, VEHICLES, AUTOMATION_INPUTS, LICENSE_COST, LICENSE_DAYS, LICENSE_INPUTS,
    expansion_quote, repair_quote,
)
from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity, production_slots, used_production_slots, factory_recipe


async def snapshot(session, owner_tg_id):
    company = await Game._owned_company(session, owner_tg_id)
    capacity = await session.get(Operations, company.id)
    land_level = capacity.land_level if capacity else 0
    warehouse_level = capacity.warehouse_level if capacity else 0
    facilities = (await session.scalars(select(NatNextGameFacility).where(
        NatNextGameFacility.company_id == company.id).order_by(NatNextGameFacility.id))).all()
    staff = (await session.scalars(select(Employee).where(Employee.company_id == company.id))).all()
    fleet = (await session.scalars(select(Vehicle).where(Vehicle.company_id == company.id))).all()
    from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService
    from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService
    bonus = await NextGameProgressionService.production_bonus(session, company)
    from backend.natbirzha.services.next_game_civic_accounting import event_multiplier
    bonus *= await event_multiplier(session, company)
    rows = []
    for facility in facilities:
        branch = find_next_game_branch(facility.branch_id)
        if not branch:
            continue
        settings = await session.get(Factory, facility.id)
        automation = settings.automation_level if settings else 0
        license_end = settings.license_expires_at if settings else None
        employees = [e for e in staff if e.facility_id == facility.id]
        vehicles = [v for v in fleet if v.facility_id == facility.id]
        base = await NextGameFusionService.facility_recipe(session, facility, branch["factory"])
        recipe = facility_recipe_at_level(base, facility.level)
        recipe["output_quantity"] = round(recipe["output_quantity"] * bonus, 4)
        recipe = await factory_recipe(session, company, facility, recipe)
        rows.append({"id": facility.id, "name": base["facility_name"], "level": facility.level,
            "branch_id": facility.branch_id, "automation_level": automation,
            "automation_quote": {"cash": 55000 * (automation + 1), "inputs": AUTOMATION_INPUTS} if automation < 5 else None,
            "license_expires_at": license_end.isoformat() + "Z" if license_end else None,
            "license_active": bool(license_end and license_end > _utcnow()),
            "license_quote": {"cash": LICENSE_COST, "inputs": LICENSE_INPUTS, "days": LICENSE_DAYS},
            "staff_slots": min(5, 2 + facility.level // 3), "fleet_slots": min(4, 1 + facility.level // 3),
            "employees": [{"id": e.id, "role": e.role, "name": EMPLOYEES[e.role]["name"],
                "salary_per_hour": EMPLOYEES[e.role]["salary_per_hour"]} for e in employees],
            "vehicles": [{"id": v.id, "type": v.vehicle_type, "name": VEHICLES[v.vehicle_type]["name"],
                "condition": v.condition, "repair_cost": repair_quote(v)} for v in vehicles],
            "available_employees": [{"id": key, **spec} for key, spec in EMPLOYEES.items()
                if company.sector_id in spec["sectors"] and facility.level >= spec["min_facility_level"]
                and key not in {e.role for e in employees}],
            "available_vehicles": [{"id": key, **spec} for key, spec in VEHICLES.items()
                if company.sector_id != "bank" and facility.level >= spec["min_facility_level"]],
            "recipe": recipe})
    return {"company_id": company.id, "cash": company.cash, "facilities": rows,
        "items": [{"id": key, **spec} for key, spec in get_next_game_items().items()],
        "capacity": {"production_slots": await production_slots(session, company.id), "used_slots": await used_production_slots(session, company.id),
            "warehouse_capacity": await warehouse_capacity(session, company.id), "land_level": land_level,
            "warehouse_level": warehouse_level, "land_quote": expansion_quote("land", land_level) if land_level < 10 else None,
            "warehouse_quote": expansion_quote("warehouse", warehouse_level) if warehouse_level < 10 else None},
        "policy": "Покупки оплачиваются казне. Зарплата, топливо и обслуживание списываются только за завершённые циклы. При перерождении штат, транспорт, лицензии и расширения прекращаются."}
