from aiogram.fsm.state import State, StatesGroup


class ApplicationForm(StatesGroup):
    age = State()
    music_role = State()
    role_details = State()
    listener_follows = State()
    listener_likes = State()
    motivation = State()
    expectations = State()
    portfolio = State()
