import pytest

from app.services.bot_text_service import TelegramHTMLValidator, validate_bot_text


def test_telegram_html_validator_accepts_balanced_supported_tags() -> None:
    TelegramHTMLValidator().validate(
        '<b>Заголовок</b> <a href="https://example.com">ссылка</a>'
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("<b>Незакрытый тег", "Не закрыт HTML-тег: <b>"),
        ("<b><i>Текст</b></i>", "Нарушен порядок закрытия HTML-тега: </b>"),
        ("<div>Текст</div>", "Неподдерживаемый HTML-тег: <div>"),
    ],
)
def test_telegram_html_validator_rejects_invalid_markup(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        TelegramHTMLValidator().validate(text)


def test_validate_bot_text_checks_html() -> None:
    with pytest.raises(ValueError, match="Не закрыт HTML-тег"):
        validate_bot_text("welcome", "<b>Привет")
