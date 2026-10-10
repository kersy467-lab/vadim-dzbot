"""Declarative tables for the isolated civilian corporation graph."""
from . import resources, energy, oilgas, materials, infrastructure, technology, bank
from .items import CUSTOM_ITEMS, EXCLUDED_ITEMS
from .legacy import CORPORATIONS as LEGACY_CORPORATIONS, RECIPES as LEGACY_RECIPES
from .legacy import NEXT_GAME_BASE_PRICES, START_BRANCH_IDS
from .legacy import NEXT_BRANCH_IDS as LEGACY_NEXT_BRANCH_IDS

SECTOR_NODES = {
    "resources": resources.NODES, "energy": energy.NODES, "oilgas": oilgas.NODES,
    "materials": materials.NODES, "infrastructure": infrastructure.NODES,
    "technology": technology.NODES, "bank": bank.NODES,
}
