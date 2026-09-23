"""Company creation constants shared by legacy and Tycoon V2 flows."""

from typing import Dict


VALID_SPECIALIZATIONS: Dict[str, str] = {
    "miner": "Горнодобывающая промышленность",
    "agrarian": "Аграрная промышленность",
    "power_engineer": "Энергетика",
    "water": "Водоснабжение",
    "oilman": "Нефтегазовая промышленность",
    "metallurgist": "Металлургия",
    "forester": "Лесопромышленность",
    "chemist": "Химическая промышленность",
    "construction": "Строительство",
    "technoprom": "Технологическая промышленность",
    "logistics": "Логистика",
}

SPECIALIZATION_ALIASES: Dict[str, str] = {
    "mining": "miner", "miner": "miner",
    "agriculture": "agrarian", "agrarian": "agrarian",
    "energy": "power_engineer", "power_engineer": "power_engineer",
    "water": "water", "infrastructure": "water", "water_utility": "water",
    "oil_gas": "oilman", "oilman": "oilman",
    "metallurgy": "metallurgist", "metallurgist": "metallurgist",
    "chemicals": "chemist", "chemist": "chemist",
    "construction": "construction", "forester": "forester", "forestry": "forester",
    "technoprom": "technoprom", "electronics": "technoprom", "it_telecom": "technoprom",
    "logistics": "logistics",
}

# Temporary compatibility factories. The active production tab uses NatBusiness;
# these rows keep old routes readable during the migration window.
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

# Extra compatibility inventory is merged with the four-hour V2 starter supply.
STARTER_INVENTORIES: Dict[str, Dict[str, float]] = {
    specialization: {"water": 25.0, "grid_quota": 25.0}
    for specialization in VALID_SPECIALIZATIONS
}

__all__ = [
    "VALID_SPECIALIZATIONS",
    "SPECIALIZATION_ALIASES",
    "STARTER_FACTORIES",
    "STARTER_INVENTORIES",
]
