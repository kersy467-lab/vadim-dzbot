"""
Main API Router for Mini App & Telegram Bot WebApp.
Decomposed into clean, maintainable modular sub-routers:
- common: /me, /bells, /subjects, /students, /duty, /facts/today, /media/{file_id}
- schedule: /schedule, /schedule/week
- homework: /homework, /homework/{hw_id}/toggle
- games: /games/classmates, /games/invite, /games/local, /games/room/*
- durak: /durak/new, /durak/join, /durak/state/*, /durak/move, /ws/durak/*
"""
from fastapi import APIRouter

from backend.api.routers import (
    common_router,
    schedule_router,
    homework_router,
    games_router,
    games_actions_router,
    durak_router,
    blackjack_router,
    roulette_router,
    dice_router,
    slots_router,
    coinflip_router,
    rpg_router,
)
from backend.api.routers.pets_system import pets_system_router
from backend.api.routers.multiplayer_hub import multiplayer_hub_router
from backend.api.routers.rebirth_engine import rebirth_engine_router
from backend.api.routers.multiplayer_market import multiplayer_market_router
from backend.api.routers.creeps_bestiary import creeps_bestiary_router
from backend.api.routers.talent_tree_router import talent_tree_router
from backend.natbirzha.api import natbirzha_router
from backend.api.auth import extract_viewer_tg_id, _extract_viewer_tg_id

api_router = APIRouter(prefix="/api")

api_router.include_router(common_router)
api_router.include_router(schedule_router)
api_router.include_router(homework_router)
api_router.include_router(games_router)
api_router.include_router(games_actions_router)
api_router.include_router(durak_router)
api_router.include_router(blackjack_router)
api_router.include_router(roulette_router)
api_router.include_router(dice_router)
api_router.include_router(slots_router)
api_router.include_router(coinflip_router)
api_router.include_router(rpg_router)
api_router.include_router(pets_system_router)
api_router.include_router(multiplayer_hub_router)
api_router.include_router(rebirth_engine_router)
api_router.include_router(multiplayer_market_router)
api_router.include_router(creeps_bestiary_router)
api_router.include_router(talent_tree_router)
api_router.include_router(natbirzha_router)
from backend.api.routers.debug import router as debug_router
api_router.include_router(debug_router)
try:
    from backend.bot.handlers.admin.pug_prank import pug_api_router
    api_router.include_router(pug_api_router)
except ImportError:
    pass


__all__ = [
    "api_router",
    "extract_viewer_tg_id",
    "_extract_viewer_tg_id",
]

