# Modular API Routers for FastAPI
from backend.api.routers.common import router as common_router
from backend.api.routers.schedule import router as schedule_router
from backend.api.routers.homework import router as homework_router
from backend.api.routers.games import router as games_router
from backend.api.routers.games_actions import router as games_actions_router
from backend.api.routers.durak import router as durak_router
from backend.api.routers.blackjack import blackjack_router
from backend.api.routers.roulette import roulette_router
from backend.api.routers.dice import dice_router
from backend.api.routers.slots import slots_router
from backend.api.routers.coinflip import coinflip_router
from backend.api.routers.heroes_dota import rpg_router
from backend.api.routers.multiplayer_hub import multiplayer_hub_router
from backend.api.routers.rebirth_engine import rebirth_engine_router
from backend.api.routers.multiplayer_market import multiplayer_market_router
from backend.api.routers.creeps_bestiary import creeps_bestiary_router
from backend.api.routers.talent_tree_router import talent_tree_router
import backend.api.routers.bosses_dynamic  # Registers combat routes onto rpg_router
import backend.api.routers.items_forge  # Registers inventory & shop routes onto rpg_router
import backend.api.routers.rpg_admin  # Registers admin management routes onto rpg_router

__all__ = [
    "common_router",
    "schedule_router",
    "homework_router",
    "games_router",
    "games_actions_router",
    "durak_router",
    "blackjack_router",
    "roulette_router",
    "dice_router",
    "slots_router",
    "coinflip_router",
    "rpg_router",
    "multiplayer_hub_router",
    "rebirth_engine_router",
    "multiplayer_market_router",
    "creeps_bestiary_router",
    "talent_tree_router",
    "debug_router",
]
from backend.api.routers.debug import router as debug_router



