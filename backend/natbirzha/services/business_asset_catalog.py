"""Small server-owned catalog for fleet, workforce and service projects."""

from types import MappingProxyType


VEHICLE_CATALOG = MappingProxyType({
    "delivery_van": {
        "name": "Городской фургон", "icon": "🚐", "tier": 1,
        "cost": 18_000.0, "output_bonus": 0.025, "maintenance_per_hour": 18.0,
        "wear_per_hour": 0.16, "min_business_stage": 1,
    },
    "cargo_truck": {
        "name": "Магистральный грузовик", "icon": "🚚", "tier": 2,
        "cost": 65_000.0, "output_bonus": 0.05, "maintenance_per_hour": 52.0,
        "wear_per_hour": 0.13, "min_business_stage": 10,
    },
    "reefer_truck": {
        "name": "Рефрижератор", "icon": "❄️", "tier": 3,
        "cost": 140_000.0, "output_bonus": 0.07, "maintenance_per_hour": 95.0,
        "wear_per_hour": 0.11, "min_business_stage": 20,
    },
    "tanker_truck": {
        "name": "Автоцистерна", "icon": "🛢️", "tier": 3,
        "cost": 175_000.0, "output_bonus": 0.075, "maintenance_per_hour": 115.0,
        "wear_per_hour": 0.11, "min_business_stage": 20,
    },
    "rail_freight_set": {
        "name": "Грузовой железнодорожный состав", "icon": "🚆", "tier": 4,
        "cost": 480_000.0, "output_bonus": 0.11, "maintenance_per_hour": 260.0,
        "wear_per_hour": 0.08, "min_business_stage": 30,
    },
    "cargo_aircraft": {
        "name": "Грузовой самолёт", "icon": "✈️", "tier": 5,
        "cost": 1_800_000.0, "output_bonus": 0.16, "maintenance_per_hour": 920.0,
        "wear_per_hour": 0.06, "min_business_stage": 40,
    },
})


EMPLOYEE_CATALOG = MappingProxyType({
    "process_engineer": {
        "name": "Инженер-технолог", "icon": "🧑‍🔧", "hire_cost": 18_000.0,
        "salary_per_hour": 65.0, "quality": 1.0, "output_bonus": 0.025,
        "specializations": ("technoprom", "construction", "metallurgist", "chemist"),
        "min_business_stage": 1,
    },
    "automation_engineer": {
        "name": "Инженер автоматизации", "icon": "🤖", "hire_cost": 55_000.0,
        "salary_per_hour": 150.0, "quality": 1.1, "output_bonus": 0.045,
        "specializations": ("technoprom", "construction"), "min_business_stage": 15,
    },
    "project_manager": {
        "name": "Руководитель проектов", "icon": "🗂️", "hire_cost": 48_000.0,
        "salary_per_hour": 135.0, "quality": 1.0, "output_bonus": 0.025,
        "specializations": ("construction", "technoprom"), "min_business_stage": 10,
    },
    "robotics_engineer": {
        "name": "Инженер-робототехник", "icon": "🦾", "hire_cost": 120_000.0,
        "salary_per_hour": 320.0, "quality": 1.2, "output_bonus": 0.075,
        "specializations": ("technoprom",), "min_business_stage": 30,
    },
    "site_supervisor": {
        "name": "Начальник участка", "icon": "👷", "hire_cost": 36_000.0,
        "salary_per_hour": 105.0, "quality": 1.0, "output_bonus": 0.035,
        "specializations": ("construction",), "min_business_stage": 8,
    },
})


PROJECT_CATALOG = MappingProxyType({
    "route_optimization": {
        "name": "Оптимизация маршрутной сети", "icon": "🗺️", "specializations": ("logistics",),
        "cost_cash": 90_000.0, "duration_hours": 3.0,
        "inputs": {"fuel_diesel": 80.0, "electronics": 4.0},
        "reward_cash": 35_000.0, "permanent_output_bonus": 0.02, "min_stage": 10,
    },
    "industrial_contract": {
        "name": "Промышленный подряд", "icon": "🏗️", "specializations": ("construction",),
        "cost_cash": 140_000.0, "duration_hours": 5.0,
        "inputs": {"concrete": 60.0, "steel": 25.0, "fuel_diesel": 40.0},
        "reward_cash": 260_000.0, "permanent_output_bonus": 0.012, "min_stage": 10,
    },
    "automation_rnd": {
        "name": "R&D промышленной автоматизации", "icon": "🧠", "specializations": ("technoprom",),
        "cost_cash": 220_000.0, "duration_hours": 8.0,
        "inputs": {"electronics": 8.0, "sensors": 6.0, "energy": 120.0},
        "reward_cash": 40_000.0, "permanent_output_bonus": 0.025, "min_stage": 15,
    },
    "robotic_cell": {
        "name": "Роботизированная производственная ячейка", "icon": "🦾", "specializations": ("technoprom",),
        "cost_cash": 650_000.0, "duration_hours": 18.0,
        "inputs": {"automation_systems": 8.0, "electronics": 12.0, "steel": 20.0},
        "reward_cash": 0.0, "permanent_output_bonus": 0.045, "min_stage": 30,
    },
})


__all__ = ["VEHICLE_CATALOG", "EMPLOYEE_CATALOG", "PROJECT_CATALOG"]
