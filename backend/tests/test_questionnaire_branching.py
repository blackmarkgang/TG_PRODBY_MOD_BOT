import pytest
from fastapi import HTTPException

from app.api.routes.configuration import validate_question_graph_data
from app.bot.handlers.application import resolve_next_question_index
from app.db.models import ApplicationQuestion


def question(
    code: str,
    order: int,
    *,
    answer_type: str = "text",
    options: list[dict] | None = None,
    next_code: str | None = None,
) -> ApplicationQuestion:
    return ApplicationQuestion(
        code=code,
        text=code,
        answer_type=answer_type,
        options_json=options or [],
        next_question_code=next_code,
        sort_order=order,
    )


def test_choice_branches_can_merge() -> None:
    questions = [
        question(
            "role",
            1,
            answer_type="single_choice",
            options=[
                {"id": "artist", "label": "Артист", "next_question_code": "artist_details"},
                {"id": "listener", "label": "Слушатель", "next_question_code": "listener_details"},
            ],
        ),
        question("artist_details", 2, next_code="motivation"),
        question("listener_details", 3, next_code="motivation"),
        question("motivation", 4, next_code="__end__"),
    ]

    validate_question_graph_data(questions)
    serialized = [{"code": item.code} for item in questions]
    assert resolve_next_question_index(serialized, 0, "listener_details") == 2
    assert resolve_next_question_index(serialized, 3, "__end__") == 4


def test_question_graph_rejects_cycle() -> None:
    questions = [
        question("first", 1, next_code="second"),
        question("second", 2, next_code="first"),
    ]

    with pytest.raises(HTTPException, match="цикл"):
        validate_question_graph_data(questions)
