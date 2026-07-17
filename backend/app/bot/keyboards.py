from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Подать заявку", callback_data="start_application")]
        ]
    )


def portfolio_keyboard(has_attachments: bool = False) -> ReplyKeyboardMarkup:
    button_text = "✅ Готово" if has_attachments else "⏭ Пропустить вложения"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=button_text)]],
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
