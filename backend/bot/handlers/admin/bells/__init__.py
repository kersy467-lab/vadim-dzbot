"""
Modular admin bells handler package.
Decomposed into:
- standard: Main bells menu, quick breaks editor, individual bell times
- date_bells: Date-specific bells, presets 30/35 min, bulk editor, notifications
- wizard: Step-by-step interactive bells builder
"""
from aiogram import Router

from backend.bot.handlers.admin.bells import (
    standard,
    date_bells,
    wizard,
)

# Re-export all handlers for 100% backward compatibility
from backend.bot.handlers.admin.bells.standard import *
from backend.bot.handlers.admin.bells.date_bells import *
from backend.bot.handlers.admin.bells.wizard import *

router = Router(name="admin_bells_router")
router.include_router(standard.router)
router.include_router(date_bells.router)
router.include_router(wizard.router)
