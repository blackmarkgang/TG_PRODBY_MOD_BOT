from types import SimpleNamespace

from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.bot.handlers.application import (
    extract_file_items,
    has_minimum_attachments,
    is_valid_text_answer,
)
from app.bot.keyboards import cache_busted_webapp_url, portfolio_keyboard


def text_message(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        caption=None,
        audio=None,
        document=None,
        video=None,
        voice=None,
        photo=None,
        text=text,
    )


def test_file_question_rejects_links_and_text() -> None:
    assert extract_file_items(text_message("https://example.com/track.mp3")) == []
    assert extract_file_items(text_message("Обычный текст")) == []


def test_text_answer_requires_ten_non_whitespace_characters() -> None:
    assert not is_valid_text_answer("")
    assert not is_valid_text_answer("  123456789  ")
    assert is_valid_text_answer("  1234567890  ")


def test_file_question_requires_two_attachments_before_finish() -> None:
    assert not has_minimum_attachments(0)
    assert not has_minimum_attachments(1)
    assert has_minimum_attachments(2)
    assert has_minimum_attachments(10)


def test_finish_button_is_hidden_until_second_attachment() -> None:
    assert isinstance(portfolio_keyboard(can_finish=False), ReplyKeyboardRemove)
    keyboard = portfolio_keyboard(can_finish=True)
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    assert keyboard.keyboard[0][0].text == "✅ Готово"


def test_webapp_url_gets_cache_busting_version() -> None:
    assert cache_busted_webapp_url("https://example.com/panel", 42) == (
        "https://example.com/panel?_v=42"
    )
    assert cache_busted_webapp_url("https://example.com/panel?tab=support", 42) == (
        "https://example.com/panel?tab=support&_v=42"
    )
