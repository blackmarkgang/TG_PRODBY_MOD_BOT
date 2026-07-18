from types import SimpleNamespace

from app.bot.handlers.application import extract_file_items


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
