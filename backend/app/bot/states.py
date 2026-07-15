from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    question = State()
    portfolio = State()
