"""Recipe effects and wear, applied only to successful production cycles."""
from sqlalchemy import delete, func, or_, select
from backend.natbirzha.models.next_game import NatNextGameFacility
from backend.natbirzha.models.next_game_partnerships import NatNextGameJointProject
from backend.natbirzha.models.next_game_operations import (
    NatNextGameOperations as Operations, NatNextGameFactoryOperations as Factory,
    NatNextGameEmployee as Employee, NatNextGameVehicle as Vehicle,
)
from backend.natbirzha.next_game_catalog import find_next_game_branch, get_next_game_items
from backend.natbirzha.services.next_game_service.common import _utcnow
from backend.natbirzha.services.next_game_operations_catalog import EMPLOYEES, VEHICLES


async def warehouse_capacity(session, company_id):
    row = await session.get(Operations, company_id)
    return 100000 + 50000 * (row.warehouse_level if row else 0)


async def production_slots(session, company_id):
    row = await session.get(Operations, company_id)
    return 12 + 4 * (row.land_level if row else 0)


async def used_production_slots(session, company_id):
    facilities = await session.scalar(select(func.count(NatNextGameFacility.id)).where(
        NatNextGameFacility.company_id == company_id)) or 0
    projects = await session.scalar(select(func.count(NatNextGameJointProject.id)).where(or_(
        (NatNextGameJointProject.status == "ACTIVE") & or_(
            NatNextGameJointProject.proposer_company_id == company_id,
            NatNextGameJointProject.partner_company_id == company_id),
        (NatNextGameJointProject.status == "OPEN") & (NatNextGameJointProject.proposer_company_id == company_id)))) or 0
    return facilities + projects


async def factory_recipe(session, company, facility, recipe, *, now=None):
    result = {**recipe, "inputs": dict(recipe["inputs"])}
    row = await session.get(Factory, facility.id)
    automation = row.automation_level if row else 0
    saving = .05 * automation
    result["inputs"] = {key: round(value * (1 - saving), 4) for key, value in recipe["inputs"].items()}
    staff = (await session.scalars(select(Employee).where(Employee.facility_id == facility.id,
        Employee.company_id == company.id))).all()
    fleet = (await session.scalars(select(Vehicle).where(Vehicle.facility_id == facility.id,
        Vehicle.company_id == company.id, Vehicle.condition > 0))).all()
    hours = recipe["cycle_seconds"] / 3600
    staff_bonus = min(.30, sum(EMPLOYEES[e.role]["output_bonus"] * EMPLOYEES[e.role]["quality"] for e in staff))
    fleet_bonus = min(.35, sum(VEHICLES[v.vehicle_type]["output_bonus"] * v.condition / 100 for v in fleet))
    salary = sum(EMPLOYEES[e.role]["salary_per_hour"] for e in staff) * hours
    maintenance = sum(VEHICLES[v.vehicle_type]["maintenance_per_hour"] for v in fleet) * hours
    for vehicle in fleet:
        spec = VEHICLES[vehicle.vehicle_type]
        key = spec["fuel_item"]
        result["inputs"][key] = round(result["inputs"].get(key, 0) + spec["fuel_per_hour"] * hours, 4)
    licensed = bool(row and row.license_expires_at and row.license_expires_at > (now or _utcnow()))
    bonus = 1 + staff_bonus + fleet_bonus + (.10 if licensed else 0)
    result["output_quantity"] = round(recipe["output_quantity"] * bonus, 4)
    result["operating_cost"] = round(recipe["operating_cost"] + salary + maintenance, 8)
    result["operations"] = {"input_saving_pct": automation * 5, "staff_bonus_pct": round(staff_bonus * 100, 3),
        "fleet_bonus_pct": round(fleet_bonus * 100, 3), "license_bonus_pct": 10 if licensed else 0,
        "salary_per_cycle": round(salary, 8), "maintenance_per_cycle": round(maintenance, 8)}
    items = get_next_game_items()
    result["net_output_quantity"] = round(result["output_quantity"] - result["inputs"].get(result["output_item"], 0), 4)
    result["input_items"] = [{"item_id": key, "name": items[key]["name"], "unit": items[key]["unit"],
        "quantity": quantity, "npc_unit_cost": round(items[key]["base_price"] * 1.2, 2),
        "npc_total_cost": round(quantity * round(items[key]["base_price"] * 1.2, 2), 2)}
        for key, quantity in result["inputs"].items()]
    cost = round(sum(item["npc_total_cost"] for item in result["input_items"]), 2)
    revenue = round(result["output_quantity"] * round(items[result["output_item"]]["base_price"] * .8, 2), 2)
    profit = round(revenue - cost - result["operating_cost"], 2)
    result["economics"] = {**recipe.get("economics", {}), "npc_input_cost": cost, "npc_revenue": revenue,
        "npc_profit": profit, "profit_per_hour": round(profit / hours, 2),
        "payback_cycles": round(recipe["build_cost"] / profit, 2) if profit > 0 else None}
    return result


async def complete_cycle(session, facility):
    branch = find_next_game_branch(facility.branch_id)
    if not branch:
        return
    from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService
    recipe = await NextGameFusionService.facility_recipe(session, facility, branch["factory"])
    hours = recipe["cycle_seconds"] / 3600
    fleet = (await session.scalars(select(Vehicle).where(Vehicle.facility_id == facility.id,
        Vehicle.company_id == facility.company_id, Vehicle.condition > 0).with_for_update())).all()
    for vehicle in fleet:
        wear = VEHICLES[vehicle.vehicle_type]["wear_per_hour"] * hours
        vehicle.condition = round(max(0, vehicle.condition - wear), 6)


async def has_factory_assets(session, facility_id):
    row = await session.get(Factory, facility_id)
    if row and (row.automation_level or row.license_expires_at and row.license_expires_at > _utcnow()):
        return True
    return bool(await session.scalar(select(Employee.id).where(Employee.facility_id == facility_id).limit(1)) or
        await session.scalar(select(Vehicle.id).where(Vehicle.facility_id == facility_id).limit(1)))


async def retire_company(session, company_id):
    for model in (Employee, Vehicle, Factory, Operations):
        await session.execute(delete(model).where(model.company_id == company_id))
    await session.flush()


async def move_factory_assets(session, source_id, target_id):
    """Preserve paid equipment when a fused factory is split into source factories."""
    for model in (Employee, Vehicle):
        rows = (await session.scalars(select(model).where(model.facility_id == source_id))).all()
        for row in rows:
            row.facility_id = target_id
    settings = await session.get(Factory, source_id)
    if settings:
        settings.facility_id = target_id
    await session.flush()
