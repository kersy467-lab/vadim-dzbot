from aiogram import Router

from backend.bot.handlers.admin.users.list import (
    router as list_router,
    cb_view_pending,
    cb_view_students,
)
from backend.bot.handlers.admin.users.rename import (
    router as rename_router,
    cb_admin_change_name_list,
    cb_admin_rename_ask,
    msg_admin_rename_save,
)
from backend.bot.handlers.admin.users.roles import (
    router as roles_router,
    cb_toggle_user_role,
    cb_toggle_user_tester,
)
from backend.bot.handlers.admin.users.delete import (
    router as delete_router,
    cb_admin_delete_user_list,
    cb_admin_delete_user_ask,
    cb_admin_delete_user_confirm,
)

router = Router(name="admin_users_router")
router.include_router(list_router)
router.include_router(rename_router)
router.include_router(roles_router)
router.include_router(delete_router)

__all__ = [
    "router",
    "cb_view_pending",
    "cb_view_students",
    "cb_admin_change_name_list",
    "cb_admin_rename_ask",
    "msg_admin_rename_save",
    "cb_toggle_user_role",
    "cb_toggle_user_tester",
    "cb_admin_delete_user_list",
    "cb_admin_delete_user_ask",
    "cb_admin_delete_user_confirm",
]
