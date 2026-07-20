"""split musician direction into artist and beatmaker

Revision ID: 0011_split_musicians
Revises: 0010_application_directions
Create Date: 2026-07-20
"""

import json

import sqlalchemy as sa
from alembic import op


revision = "0011_split_musicians"
down_revision = "0010_application_directions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    row = connection.execute(
        sa.text(
            "SELECT id, options_json FROM application_questions "
            "WHERE code = 'role_details'"
        )
    ).mappings().first()
    if row is None:
        return

    options = list(row["options_json"] or [])
    musician = next(
        (option for option in options if option.get("label") == "Музыкант"),
        None,
    )
    if musician is None:
        return

    musician["id"] = "artist"
    musician["label"] = "Артист"
    if not any(option.get("id") == "beatmaker" for option in options):
        options.insert(
            options.index(musician) + 1,
            {
                "id": "beatmaker",
                "label": "Битмейкер",
                "next_question_code": musician.get("next_question_code"),
            },
        )
    _save_options(connection, row["id"], options)


def downgrade() -> None:
    connection = op.get_bind()
    row = connection.execute(
        sa.text(
            "SELECT id, options_json FROM application_questions "
            "WHERE code = 'role_details'"
        )
    ).mappings().first()
    if row is None:
        return

    options = [
        option for option in (row["options_json"] or []) if option.get("id") != "beatmaker"
    ]
    artist = next((option for option in options if option.get("id") == "artist"), None)
    if artist is not None:
        artist["id"] = "musician"
        artist["label"] = "Музыкант"
    _save_options(connection, row["id"], options)


def _save_options(connection, question_id: int, options: list[dict]) -> None:
    connection.execute(
        sa.text(
            "UPDATE application_questions SET options_json = CAST(:options AS jsonb) "
            "WHERE id = :question_id"
        ),
        {"options": json.dumps(options, ensure_ascii=False), "question_id": question_id},
    )
