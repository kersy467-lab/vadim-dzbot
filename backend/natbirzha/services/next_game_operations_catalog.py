"""Ported fleet/staff prices and explicit civilian production effects."""
from math import ceil
from backend.natbirzha.services.business_asset_catalog import EMPLOYEE_CATALOG, VEHICLE_CATALOG

VEHICLES = {key: {**value, "min_facility_level": min(10, max(1, ceil(value["min_business_stage"] / 5))),
    "fuel_item": "jet_fuel" if key == "cargo_aircraft" else "fuel_diesel",
    "fuel_per_hour": {"delivery_van": 1, "cargo_truck": 3, "reefer_truck": 4,
        "tanker_truck": 5, "rail_freight_set": 10, "cargo_aircraft": 15}[key]}
    for key, value in VEHICLE_CATALOG.items()}
SECTORS = {"process_engineer": ["resources", "energy", "oilgas", "materials", "infrastructure", "technology"],
    "automation_engineer": ["technology", "infrastructure"],
    "project_manager": ["technology", "infrastructure"], "robotics_engineer": ["technology"],
    "site_supervisor": ["infrastructure"]}
EMPLOYEES = {key: {**value, "sectors": SECTORS[key],
    "min_facility_level": min(10, max(1, ceil(value["min_business_stage"] / 5)))}
    for key, value in EMPLOYEE_CATALOG.items()}
AUTOMATION_INPUTS = {"electronics": 2, "steel": 5}
LICENSE_COST = 25000
LICENSE_DAYS = 7
LICENSE_INPUTS = {"electronics": 1}


def expansion_quote(kind, level):
    return {"cash": (25000 if kind == "land" else 20000) * (level + 1) ** 2,
            "inputs": {"concrete": 10 * (level + 1), "steel": 5 * (level + 1)}}


def repair_quote(vehicle):
    missing = max(0, 100 - vehicle.condition)
    return max(.01, round(VEHICLES[vehicle.vehicle_type]["cost"] * .006 * missing, 2)) if missing else 0
