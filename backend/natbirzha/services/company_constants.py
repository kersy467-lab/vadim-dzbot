from typing import Dict

VALID_SPECIALIZATIONS: Dict[str, str] = {
    "agrarian": "Аграрий",
    "miner": "Горнодобытчик",
    "metallurgist": "Металлург",
    "oilman": "Нефтяник",
    "power_engineer": "Энергетик",
    "forester": "Лесопромышленник",
    "chemist": "Химик",
    "technoprom": "Технопром",
}

SPECIALIZATION_ALIASES: Dict[str, str] = {
    "metallurgy": "metallurgist",
    "metallurgist": "metallurgist",
    "energy": "power_engineer",
    "power_engineer": "power_engineer",
    "oil_gas": "oilman",
    "oilman": "oilman",
    "agriculture": "agrarian",
    "agrarian": "agrarian",
    "chemicals": "chemist",
    "chemist": "chemist",
    "forester": "forester",
    "forestry": "forester",
    "miner": "miner",
    "mining": "miner",
    "technoprom": "technoprom",
    "electronics": "technoprom",
    "construction": "miner",
    "it_telecom": "technoprom",
}

STARTER_FACTORIES: Dict[str, str] = {
    "agrarian": "farm_grain",
    "miner": "iron_mine",
    "metallurgist": "steel_mill",
    "oilman": "oil_rig",
    "power_engineer": "solar_plant",
    "forester": "logging_camp",
    "chemist": "chemical_plant",
    "technoprom": "component_factory",
}

STARTER_INVENTORIES: Dict[str, Dict[str, float]] = {
    "agrarian": {"water": 100.0, "grid_quota": 100.0},
    "miner": {"water": 100.0, "grid_quota": 100.0},
    "oilman": {"water": 100.0, "grid_quota": 100.0},
    "forester": {"water": 100.0, "grid_quota": 100.0},
    "power_engineer": {"water": 100.0, "grid_quota": 100.0},
    "metallurgist": {"water": 100.0, "grid_quota": 100.0, "iron_ore": 60.0, "coal": 40.0, "energy": 60.0},
    "chemist": {"water": 100.0, "grid_quota": 100.0, "oil_crude": 40.0, "energy": 60.0},
    "technoprom": {"water": 100.0, "grid_quota": 100.0, "copper": 40.0, "plastics": 40.0, "energy": 60.0},
}

__all__ = [
    "VALID_SPECIALIZATIONS",
    "SPECIALIZATION_ALIASES",
    "STARTER_FACTORIES",
    "STARTER_INVENTORIES",
]
