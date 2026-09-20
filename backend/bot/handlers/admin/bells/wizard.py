"""
Bell schedule wizard package module.
Composed of:
- wizard_target: Target mode selection (permanent vs date) and calendar date picker
- wizard_params: Steps 1-3 (count 1-8, arbitrary start time, arbitrary lesson duration)
- wizard_breaks: Step 4-5 (individual break customization, bulk input, templates, confirm & save)
"""
from aiogram import Router

from backend.bot.handlers.admin.bells import wizard_target, wizard_params, wizard_breaks

# Re-export all functions and symbols for 100% backward compatibility
from backend.bot.handlers.admin.bells.wizard_target import *
from backend.bot.handlers.admin.bells.wizard_params import *
from backend.bot.handlers.admin.bells.wizard_breaks import *

router = Router(name="admin_bells_wiz_router")
router.include_router(wizard_target.router)
router.include_router(wizard_params.router)
router.include_router(wizard_breaks.router)
