"""
Modular admin homework handler package.
Decomposed into:
- helpers: Subject aliases, icons, date suggestions, markup generators
- add: Add homework wizard, calendar picking, multi-media collector
- actions: Notification broadcasting and homework deletion
"""
from aiogram import Router

from backend.bot.handlers.admin.homework import (
    helpers,
    add,
    actions,
)

# Re-export all handlers and helpers for 100% backward compatibility
from backend.bot.handlers.admin.homework.helpers import *
from backend.bot.handlers.admin.homework.add import *
from backend.bot.handlers.admin.homework.actions import *

router = Router(name="admin_homework_router")
router.include_router(add.router)
router.include_router(actions.router)
