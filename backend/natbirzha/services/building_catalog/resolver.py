from typing import Dict, Any, List, Optional
from backend.natbirzha.models.company import NatCompany

BUILDING_ALIASES: Dict[str, str] = {
    'farm': 'farm_grain',
    'mine': 'iron_mine',
    'smelter': 'steel_mill',
    'metallurgy_smelter': 'steel_mill',
    'coal_power_plant': 'thermal_power_plant',
    'thermal_plant': 'thermal_power_plant',
    'hydro_solar': 'solar_plant',
    'chem_plant': 'chemical_plant',
    'polymer_plant': 'polymer_factory',
    'deep_mine': 'lithium_mine',
    'uranium_quarry': 'uranium_mine',
    'machinery_plant': 'component_factory',
    'electronics_fab': 'chip_factory',
    'centrifuge': 'chip_factory',
    'defense_plant': 'machine_factory',
}

def resolve_building_type(raw_type: Optional[str]) -> str:
    if not raw_type:
        return ''
    cleaned = raw_type.strip().lower()
    return BUILDING_ALIASES.get(cleaned, cleaned)

def list_catalog_for_company(all_buildings: Dict[str, Dict[str, Any]], company: Optional[NatCompany]) -> List[Dict[str, Any]]:
    res = []
    comp_spec = company.specialization if company else None
    comp_level = company.level if company else 1
    comp_cash = company.cash if company else 0.0
    licensed_spec = company.licensed_foreign_spec if company else None

    for b_id, b in all_buildings.items():
        is_own = (b['specialization'] == comp_spec)
        is_licensed = (licensed_spec == b['specialization'])
        eff = 1.0 if is_own else (0.12 if is_licensed else 0.10)
        unlocked = comp_level >= b['level_required']
        can_afford = comp_cash >= b['build_cost']

        res.append({
            **b,
            'is_own_specialization': is_own,
            'efficiency': eff,
            'unlocked': unlocked,
            'can_afford': can_afford,
            'status': 'available' if (unlocked and can_afford) else ('need_level' if not unlocked else 'need_cash')
        })
    return res
