import pytest

from app.api.routes.applications import get_application_role_code
from app.db.models import Application


@pytest.mark.parametrize(
    ("direction", "role_code"),
    [
        ("Артист", "artist"),
        ("Битмейкер", "beatmaker"),
        ("Слушатель", "listener"),
        (
            "Креативный продакшн (видео, дизайн, монтаж)",
            "creative_production",
        ),
        ("Музыкант", None),
    ],
)
def test_application_direction_maps_to_role(
    direction: str,
    role_code: str | None,
) -> None:
    application = Application(answers_json={"role_details": direction})

    assert get_application_role_code(application) == role_code
