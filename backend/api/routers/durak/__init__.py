"""
Пакет API роутера игры «Дурак».
100% обратная совместимость с backend.api.routers.durak.
"""
from .router import router
from .state import (
    _durak_rooms,
    _durak_check_settlement,
    _durak_leave_room,
    _durak_broadcast,
    _durak_bot_auto_move,
)

__all__ = [
    "router",
    "_durak_rooms",
    "_durak_check_settlement",
    "_durak_leave_room",
    "_durak_broadcast",
    "_durak_bot_auto_move",
]
