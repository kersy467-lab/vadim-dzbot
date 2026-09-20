from typing import Any, Dict, Optional

from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.services.building_catalog import CANONICAL_BUILDINGS

# Only canonical recipes are exposed to gameplay. Legacy IDs are accepted only
# as input aliases for backwards compatibility and never appear in RECIPES.
LEGACY_RECIPE_ALIASES: Dict[str, str] = {
    "food_processing": "produce_rations",
    "mine_coal_iron": "mine_iron",
    "mine_rare_lithium": "mine_lithium",
    "mine_uranium": "mine_uranium_raw",
    "log_timber": "log_timber_camp",
    "mill_lumber": "saw_lumber",
    "pump_oil_gas": "pump_oil_crude",
    "refine_fuel": "refine_fuels",
    "generate_solar_hydro": "generate_solar",
    "generate_thermal": "generate_thermal_plant",
    "generate_nuclear": "generate_nuclear_plant",
    "smelt_steel": "smelt_steel_mill",
    "smelt_aluminum": "roll_metal",
    "synth_chem_fertilizer": "chem_synth_base",
    "polymer_synthesis": "chem_polymers",
    "manufacture_machinery": "assemble_machinery",
    "manufacture_electronics": "tech_chips",
}


def _build_recipes() -> Dict[str, Dict[str, Any]]:
    recipes: Dict[str, Dict[str, Any]] = {}
    for building_id, building in CANONICAL_BUILDINGS.items():
        recipe_id = building["recipe_id"]
        if recipe_id in recipes:
            raise ValueError(f"Duplicate canonical recipe_id: {recipe_id}")
        for item_id in (*building["inputs"].keys(), *building["outputs"].keys()):
            if item_id not in CANONICAL_ITEMS:
                raise ValueError(f"Unknown canonical item_id {item_id!r} in recipe {recipe_id}")
        recipes[recipe_id] = {
            "recipe_id": recipe_id,
            "factory_type": building_id,
            "specialization": building["specialization"],
            "level_req": building["level_required"],
            "unlock_level": building["level_required"],
            "name": building["name"],
            "inputs": dict(building["inputs"]),
            "outputs": dict(building["outputs"]),
            "base_duration": building["cycle_duration"],
            "duration": building["cycle_duration"],
            "energy_cost": building["energy_required"],
            "labor_demand": building["workers_required"],
            "required_license": building.get("required_license"),
        }
    return recipes


RECIPES: Dict[str, Dict[str, Any]] = _build_recipes()


def resolve_recipe_id(recipe_id: Optional[str]) -> Optional[str]:
    if not recipe_id:
        return None
    return LEGACY_RECIPE_ALIASES.get(recipe_id, recipe_id)


def get_recipe(recipe_id: Optional[str]) -> Optional[Dict[str, Any]]:
    canonical_id = resolve_recipe_id(recipe_id)
    return RECIPES.get(canonical_id) if canonical_id else None


def get_recipe_for_factory(factory_type: str) -> Optional[Dict[str, Any]]:
    return next((r for r in RECIPES.values() if r["factory_type"] == factory_type), None)


def validate_recipe_dag() -> bool:
    """Validate the canonical production graph as a strict DAG."""
    graph: Dict[str, set[str]] = {}
    for recipe in RECIPES.values():
        inputs = set(recipe.get("inputs", {}).keys())
        for output in recipe.get("outputs", {}).keys():
            graph.setdefault(output, set()).update(inputs)

    visited: set[str] = set()
    stack: set[str] = set()

    def has_cycle(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, ()):
            if neighbor not in visited and has_cycle(neighbor):
                return True
            if neighbor in stack:
                return True
        stack.remove(node)
        return False

    for node in graph:
        if node not in visited and has_cycle(node):
            raise ValueError(f"Cycle detected in production graph around node {node}!")
    return True


__all__ = [
    "RECIPES",
    "LEGACY_RECIPE_ALIASES",
    "resolve_recipe_id",
    "get_recipe",
    "get_recipe_for_factory",
    "validate_recipe_dag",
]
