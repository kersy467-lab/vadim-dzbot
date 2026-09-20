from aiogram.fsm.state import State, StatesGroup


class AddHomeworkStates(StatesGroup):
    choosing_subject = State()
    entering_content = State()
    entering_date = State()


class AddSubstitutionStates(StatesGroup):
    entering_date = State()
    entering_lesson_num = State()
    choosing_action = State()
    choosing_new_subject = State()
    entering_comment = State()
    confirm_notification = State()


class EditScheduleStates(StatesGroup):
    choosing_day = State()
    choosing_lesson = State()
    choosing_subject = State()
    entering_text_bulk = State()


class EditDateScheduleStates(StatesGroup):
    choosing_date = State()
    choosing_lesson = State()
    choosing_subject = State()
    entering_text_bulk = State()
    confirm_notification = State()


class ManageDutyStates(StatesGroup):
    choosing_group_to_edit = State()
    selecting_members_buttons = State()
    entering_members = State()


class ApproveUserStates(StatesGroup):
    entering_name = State()


class RenameUserStates(StatesGroup):
    entering_name = State()


class EditBellStates(StatesGroup):
    choosing_lesson = State()
    entering_times = State()


class EditDateBellStates(StatesGroup):
    choosing_date = State()
    entering_text_bulk = State()
    confirm_notification = State()


class EditBreakStates(StatesGroup):
    choosing_lesson = State()
    choosing_duration = State()


class SubjectManagementStates(StatesGroup):
    entering_new_name = State()


class ScheduleWizardStates(StatesGroup):
    choosing_lesson_count = State()
    choosing_subject_for_lesson = State()


class BellWizardStates(StatesGroup):
    choosing_target = State()
    choosing_date = State()
    choosing_count = State()
    choosing_start = State()
    choosing_duration = State()
    choosing_break = State()
    choosing_lunch = State()
    configuring_breaks = State()
    editing_single_break = State()
    confirm_save = State()


class BroadcastStates(StatesGroup):
    entering_message = State()
    confirm_destination = State()


class DutyBroadcastStates(StatesGroup):
    entering_message = State()
    confirm_destination = State()


class ScheduleBroadcastStates(StatesGroup):
    choosing_date = State()
    confirm_destination = State()

