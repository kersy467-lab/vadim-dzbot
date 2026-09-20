"""
Admin homework adding wizard aggregator module.
Composed of:
- add_picker: Subject selection, date selection, and calendar date picking
- add_content: Media/text content collection, debounce, and final save
"""
from aiogram import Router

from backend.bot.handlers.admin.homework import add_picker, add_content

# Re-export all handlers and functions for 100% backward compatibility
from backend.bot.handlers.admin.homework.add_picker import *
from backend.bot.handlers.admin.homework.add_content import *

router = Router(name="admin_homework_add_router")
router.include_router(add_picker.router)
router.include_router(add_content.router)
