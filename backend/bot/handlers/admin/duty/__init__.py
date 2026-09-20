"""
Modular admin duty handler package.
Decomposed into:
- roster: Duty roster, groups view, member management, active group override
- broadcast: Duty announcements and targeted broadcasting
"""
from aiogram import Router

from backend.bot.handlers.admin.duty import (
    roster,
    broadcast,
)

# Re-export all handlers for 100% backward compatibility
from backend.bot.handlers.admin.duty.roster import *
from backend.bot.handlers.admin.duty.broadcast import *

router = Router(name="admin_duty_router")
router.include_router(roster.router)
router.include_router(broadcast.router)
