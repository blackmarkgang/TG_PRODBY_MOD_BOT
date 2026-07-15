from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

ROLE_LABELS = [
    "Артист",
    "Битмейкер / Продюсер",
    "Звукоинженер",
    "Монтажер",
    "Дизайнер",
    "Слушатель",
    "Другое",
]


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подать заявку", callback_data="start_application")]
        ]
    )


def roles_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=role)] for role in ROLE_LABELS],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def portfolio_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Готово")]],
        resize_keyboard=True,
    )
