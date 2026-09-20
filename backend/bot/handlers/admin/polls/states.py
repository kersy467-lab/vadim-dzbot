from aiogram.fsm.state import State, StatesGroup

class PollWizardStates(StatesGroup):
    entering_question = State()
    entering_options = State()
    configuring_settings = State()
