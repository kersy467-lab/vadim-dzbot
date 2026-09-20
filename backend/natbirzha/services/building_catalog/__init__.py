from typing import Dict, Any, List, Optional
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.building_catalog.buildings_part1 import PART1_BUILDINGS
from backend.natbirzha.services.building_catalog.buildings_part2 import PART2_BUILDINGS
from backend.natbirzha.services.building_catalog.resolver import (
    BUILDING_ALIASES, resolve_building_type, list_catalog_for_company as _list_catalog
)

CANONICAL_BUILDINGS: Dict[str, Dict[str, Any]] = {
    **PART1_BUILDINGS,
    **PART2_BUILDINGS
}

def get_building_spec(b_type: str) -> Optional[Dict[str, Any]]:
    canonical = resolve_building_type(b_type)
    return CANONICAL_BUILDINGS.get(canonical)

def list_catalog_for_company(company: Optional[NatCompany]) -> List[Dict[str, Any]]:
    return _list_catalog(CANONICAL_BUILDINGS, company)

__all__ = [
    'CANONICAL_BUILDINGS',
    'BUILDING_ALIASES',
    'resolve_building_type',
    'get_building_spec',
    'list_catalog_for_company'
]
