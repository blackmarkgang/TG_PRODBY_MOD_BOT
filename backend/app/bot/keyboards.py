from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Подать заявку", callback_data="start_application")]
        ]
    )


def portfolio_keyboard(can_finish: bool = False) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if not can_finish:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Готово")]],
        resize_keyboard=True,
    )


def question_choice_keyboard(question_code: str, options: list[dict]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=option["label"],
                    callback_data=f"question_choice:{question_code}:{option['id']}",
                )
            ]
            for option in options
        ]
    )
