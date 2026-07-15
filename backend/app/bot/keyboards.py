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
