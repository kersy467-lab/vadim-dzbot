"""
Modular admin schedule handler package.
Decomposed into:
- permanent: Permanent weekly schedule management
- date_override: Date-specific schedule overrides and resets
- wizard: Step-by-step interactive schedule builder
- substitutions: Substitutions, cancellations and schedule broadcast
"""
from aiogram import Router

from backend.bot.handlers.admin.schedule import (
    permanent,
    date_override,
    wizard,
    substitutions,
)

# Re-export all handlers for 100% backward compatibility
from backend.bot.handlers.admin.schedule.permanent import *
from backend.bot.handlers.admin.schedule.date_override import *
from backend.bot.handlers.admin.schedule.wizard import *
from backend.bot.handlers.admin.schedule.substitutions import *

router = Router(name="admin_schedule_router")
router.include_router(permanent.router)
router.include_router(date_override.router)
router.include_router(wizard.router)
router.include_router(substitutions.router)
