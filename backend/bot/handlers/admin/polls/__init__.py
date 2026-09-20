from aiogram import Router

from backend.bot.handlers.admin.polls.create import router as create_router
from backend.bot.handlers.admin.polls.manage import (
    router as manage_router,
    cb_admin_polls_menu,
    cb_admin_poll_view,
    cb_admin_poll_nonvoters,
    cb_admin_poll_remind,
    cb_admin_poll_close,
    cb_admin_poll_delete,
)

router = Router(name="admin_polls_router")
router.include_router(create_router)
router.include_router(manage_router)

__all__ = [
    "router",
    "cb_admin_polls_menu",
    "cb_admin_poll_view",
    "cb_admin_poll_nonvoters",
    "cb_admin_poll_remind",
    "cb_admin_poll_close",
    "cb_admin_poll_delete",
]
