# Package backend.bot.handlers.admin
# Modular Admin Panel with sub-routers for 100% maintainability and zero circular dependencies.

from aiogram import Router

from backend.bot.handlers.admin.states import (
    AddHomeworkStates,
    AddSubstitutionStates,
    EditScheduleStates,
    EditDateScheduleStates,
    ManageDutyStates,
    ApproveUserStates,
    RenameUserStates,
    EditBellStates,
    EditDateBellStates,
    EditBreakStates,
    SubjectManagementStates,
    ScheduleWizardStates,
    BellWizardStates,
    BroadcastStates,
    DutyBroadcastStates,
)

from backend.bot.handlers.admin.helpers import (
    is_admin,
    parse_schedule_text,
    parse_bells_text,
)

from backend.bot.handlers.admin import (
    menu,
    subjects,
    duty,
    bells,
    schedule,
    homework,
    users,
    broadcast,
    logging as admin_logging,
    coins as admin_coins,
    polls as admin_polls,
)

# Re-export handlers for backward compatibility with tests
from backend.bot.handlers.admin.menu import (
    show_admin_panel,
    cb_admin_menu_back,
    cb_admin_cancel,
    cmd_test_digest,
)
from backend.bot.handlers.admin.subjects import (
    cb_manage_subjects,
    cb_start_add_subject,
    msg_save_subject,
    cb_start_del_subject,
    cb_confirm_del_subject,
)
from backend.bot.handlers.admin.duty import (
    cb_admin_manage_duty,
    cb_admin_duty_clear_all,
    cb_admin_duty_pick_active,
    cb_admin_duty_set,
    cb_admin_duty_pick_edit,
    cb_admin_duty_edit_chosen,
    msg_admin_duty_save_members,
    cb_admin_duty_broadcast_start,
    msg_admin_duty_broadcast_text,
    cb_admin_duty_broadcast_send,
)
from backend.bot.handlers.admin.bells import (
    cb_bells_menu,
    cb_quick_breaks_lesson_pick,
    cb_quick_breaks_duration_pick,
    cb_save_quick_break,
    cb_start_edit_bells,
    cb_edit_bell_chosen,
    msg_edit_bell_save,
    cb_admin_date_bells,
    cb_dtb_preset_35,
    cb_dtb_preset_30,
    cb_dtb_bulk_prompt,
    msg_dtb_bulk_save,
    cb_dtb_reset,
    cb_dtb_notify_yes,
    cb_dtb_notify_no,
    cb_bell_wizard_start,
    cb_bell_wizard_save,
)
from backend.bot.handlers.admin.schedule import (
    cb_start_edit_schedule,
    cb_edit_sched_day_chosen,
    cb_edit_sched_bulk_prompt,
    msg_edit_sched_bulk_save,
    cb_edit_sched_single_lessons,
    cb_edit_sched_lesson_chosen,
    cb_edit_sched_save,
    cb_start_edit_date_schedule,
    cb_cal_act_adm_dtsched,
    cb_edit_dt_sched_bulk_prompt,
    msg_edit_dt_sched_bulk_save,
    cb_edit_dt_sched_single_pick,
    cb_edit_dt_sched_lesson_chosen,
    cb_edit_dt_sched_save,
    cb_edit_dt_sched_reset,
    cb_edit_dt_notify_yes,
    cb_edit_dt_notify_no,
    cb_start_add_sub,
    cb_sub_broadcast,
    cb_sub_no_broadcast,
)
from backend.bot.handlers.admin.homework import (
    cb_start_add_hw,
    cb_add_hw_subject_chosen,
    cb_add_hw_date_chosen,
    cb_add_hw_open_cal,
    msg_add_hw_date_text,
    msg_add_hw_collect_content,
    cb_add_hw_save_now,
    cb_hw_notif_group,
    cb_hw_notif_all,
    cb_hw_notif_none,
    cb_start_delete_hw,
    cb_confirm_delete_hw,
    cb_hw_delete,
)
from backend.bot.handlers.admin.users import (
    cb_view_pending,
    cb_view_students,
    cb_toggle_user_role,
    cb_admin_delete_user_list,
    cb_admin_delete_user_ask,
    cb_admin_delete_user_confirm,
)
from backend.bot.handlers.admin.broadcast import (
    cb_admin_broadcast_custom_start,
    msg_admin_broadcast_text,
    cb_admin_broadcast_send,
)

# Root admin router combining all sub-routers
router = Router(name="admin_root_router")

router.include_router(menu.router)
router.include_router(subjects.router)
router.include_router(duty.router)
router.include_router(bells.router)
router.include_router(schedule.router)
router.include_router(homework.router)
router.include_router(users.router)
router.include_router(broadcast.router)
router.include_router(admin_logging.router)
router.include_router(admin_coins.router)
router.include_router(admin_polls.router)
try:
    from backend.bot.handlers.admin import pug_prank
    router.include_router(pug_prank.router)
except ImportError:
    pass

__all__ = [
    "router",
    "is_admin",
    "parse_schedule_text",
    "parse_bells_text",
    "AddHomeworkStates",
    "AddSubstitutionStates",
    "EditScheduleStates",
    "EditDateScheduleStates",
    "ManageDutyStates",
    "EditBellStates",
    "EditDateBellStates",
    "EditBreakStates",
    "SubjectManagementStates",
    "ScheduleWizardStates",
    "BellWizardStates",
    "BroadcastStates",
    "DutyBroadcastStates",
    "show_admin_panel",
    "cb_admin_manage_duty",
    "cb_admin_duty_set",
    "cb_admin_duty_broadcast_start",
    "cb_admin_delete_user_ask",
    "cb_admin_delete_user_confirm",
]
