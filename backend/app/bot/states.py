from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    question = State()
    file_upload = State()


class SupportForm(StatesGroup):
    description = State()
    reply = State()
