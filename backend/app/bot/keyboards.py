from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Submit application")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

