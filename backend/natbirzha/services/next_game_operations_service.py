"""Owner authorized purchases paid to the finite 2.0 reserve bank."""
from datetime import timedelta
from sqlalchemy import func, select
from backend.natbirzha.models.next_game import NatNextGameFacility
from backend.natbirzha.models.next_game_operations import (
    NatNextGameOperations as Operations, NatNextGameFactoryOperations as Factory,
    NatNextGameEmployee as Employee, NatNextGameVehicle as Vehicle,
)
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_market_service import NextGameMarketService as Market
from backend.natbirzha.services.next_game_service.common import _utcnow
from backend.natbirzha.services.next_game_operations_catalog import (
    EMPLOYEES, VEHICLES, AUTOMATION_INPUTS, LICENSE_COST, LICENSE_DAYS, LICENSE_INPUTS,
    expansion_quote, repair_quote,
)
from backend.natbirzha.services.next_game_operations_effects import (
    warehouse_capacity, production_slots, factory_recipe, complete_cycle, retire_company, has_factory_assets,
)


async def pay(session, company, cash, inputs, action, metadata=None):
    if company.cash + 1e-8 < cash:
        raise ValueError(f"Требуется {cash:g} cash")
    for item, quantity in inputs.items():
        row = await Game._inventory_row(session, company.id, item)
        if not row or row.quantity + 1e-8 < quantity:
            raise ValueError(f"Недостаточно свободного сырья: {item}, требуется {quantity:g}")
    treasury = await Game._treasury(session)
    company.cash = round(company.cash - cash, 8)
    treasury.cash = round(treasury.cash + cash, 8)
    session.add(Game._ledger(company.id, action, -cash, cash, metadata=metadata or {}))
    for item, quantity in inputs.items():
        await Game._change_inventory(session, company.id, item, -quantity)
        session.add(Game._ledger(company.id, "OPERATIONS_INPUT", 0, 0, item_id=item,
            company_quantity=-quantity, metadata=metadata or {}))


async def owned_factory(session, company, facility_id):
    facility = await session.scalar(select(NatNextGameFacility).where(
        NatNextGameFacility.id == facility_id, NatNextGameFacility.company_id == company.id).with_for_update())
    if not facility:
        raise ValueError("Собственное предприятие не найдено")
    return facility


async def factory_settings(session, company, facility):
    row = await session.get(Factory, facility.id)
    if row is None:
        row = Factory(facility_id=facility.id, company_id=company.id, automation_level=0)
        session.add(row)
        await session.flush()
    return row


async def operate(session, owner_tg_id, action, facility_id=None, asset_id=None, kind=None):
    await Market.lock_orderbook(session)
    company = await Game._owned_company(session, owner_tg_id)
    # Settle at the old modifiers before changing the paid production equipment.
    await Game.settle_company(session, owner_tg_id)
    if action in {"LAND", "WAREHOUSE"}:
        row = await session.get(Operations, company.id)
        level = getattr(row, "land_level" if action == "LAND" else "warehouse_level", 0)
        if level >= 10:
            raise ValueError("Достигнут предел расширения")
        quote = expansion_quote(action.lower(), level)
        await pay(session, company, quote["cash"], quote["inputs"], action + "_EXPAND")
        if row is None:
            row = Operations(company_id=company.id, land_level=0, warehouse_level=0)
            session.add(row)
        setattr(row, "land_level" if action == "LAND" else "warehouse_level", level + 1)
    elif action in {"FIRE", "REPAIR", "SCRAP"}:
        model = Employee if action == "FIRE" else Vehicle
        asset = await session.scalar(select(model).where(model.id == asset_id,
            model.company_id == company.id).with_for_update())
        if not asset:
            raise ValueError("Собственный актив не найден")
        await owned_factory(session, company, asset.facility_id)
        if action == "REPAIR":
            if asset.condition >= 100:
                raise ValueError("Транспорт уже исправен")
            await pay(session, company, repair_quote(asset), {}, "FLEET_REPAIR", {"vehicle_id": asset.id})
            asset.condition = 100
        else:
            session.add(Game._ledger(company.id, "OPERATIONS_RETIRE", 0, 0,
                metadata={"action": action, "asset_id": asset.id, "facility_id": asset.facility_id}))
            await session.delete(asset)
    else:
        facility = await owned_factory(session, company, facility_id)
        if action in {"AUTOMATION", "LICENSE"}:
            row = await factory_settings(session, company, facility)
            if action == "AUTOMATION":
                if row.automation_level >= 5:
                    raise ValueError("Достигнут предел автоматизации: экономия сырья 25%")
                await pay(session, company, 55000 * (row.automation_level + 1), AUTOMATION_INPUTS,
                    "FACTORY_AUTOMATE", {"facility_id": facility.id})
                row.automation_level += 1
            else:
                if row.license_expires_at and row.license_expires_at > _utcnow():
                    raise ValueError("Лицензия ещё действует")
                await pay(session, company, LICENSE_COST, LICENSE_INPUTS, "FACTORY_LICENSE", {"facility_id": facility.id})
                row.license_expires_at = _utcnow() + timedelta(days=LICENSE_DAYS)
        elif action == "HIRE":
            spec = EMPLOYEES.get(kind)
            if not spec or company.sector_id not in spec["sectors"] or facility.level < spec["min_facility_level"]:
                raise ValueError("Эта должность недоступна отрасли или уровню предприятия")
            if await session.scalar(select(Employee.id).where(Employee.facility_id == facility.id, Employee.role == kind)):
                raise ValueError("Эта должность уже занята")
            count = await session.scalar(select(func.count(Employee.id)).where(Employee.facility_id == facility.id))
            if count >= min(5, 2 + facility.level // 3):
                raise ValueError("Все штатные места заняты")
            await pay(session, company, spec["hire_cost"], {}, "EMPLOYEE_HIRE", {"facility_id": facility.id, "role": kind})
            session.add(Employee(facility_id=facility.id, company_id=company.id, role=kind))
        elif action == "VEHICLE":
            spec = VEHICLES.get(kind)
            if not spec or company.sector_id == "bank" or facility.level < spec["min_facility_level"]:
                raise ValueError("Транспорт недоступен отрасли или уровню предприятия")
            count = await session.scalar(select(func.count(Vehicle.id)).where(Vehicle.facility_id == facility.id))
            if count >= min(4, 1 + facility.level // 3):
                raise ValueError("Все места автопарка заняты")
            await pay(session, company, spec["cost"], {}, "FLEET_BUY", {"facility_id": facility.id, "type": kind})
            session.add(Vehicle(facility_id=facility.id, company_id=company.id, vehicle_type=kind, condition=100))
        else:
            raise ValueError("Неизвестная операция")
    await session.flush()
    return {"success": True, "cash": company.cash, "action": action}


class NextGameOperationsService:
    operate = staticmethod(operate)
    warehouse_capacity = staticmethod(warehouse_capacity)
    production_slots = staticmethod(production_slots)
    factory_recipe = staticmethod(factory_recipe)
    complete_cycle = staticmethod(complete_cycle)
    retire_company = staticmethod(retire_company)
    has_factory_assets = staticmethod(has_factory_assets)
