"""split application directions into three choices

Revision ID: 0010_application_directions
Revises: 0009_file_question
Create Date: 2026-07-18
"""

import json

import sqlalchemy as sa
from alembic import op


revision = "0010_application_directions"
down_revision = "0009_file_question"
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
        (option for option in options if "музыкант" in option.get("label", "").casefold()),
        None,
    )
    if musician is not None:
        musician["label"] = "Музыкант"
    if not any("креатив" in option.get("label", "").casefold() for option in options):
        options.append(
            {
                "id": "creative_prod",
                "label": "Креативный продакшн (видео, дизайн, монтаж)",
                "next_question_code": (
                    musician.get("next_question_code") if musician else "expectations"
                ),
            }
        )
    connection.execute(
        sa.text(
            "UPDATE application_questions SET options_json = CAST(:options AS jsonb) "
            "WHERE id = :question_id"
        ),
        {"options": json.dumps(options, ensure_ascii=False), "question_id": row["id"]},
    )


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
        option
        for option in (row["options_json"] or [])
        if option.get("id") != "creative_prod"
    ]
    for option in options:
        if option.get("label") == "Музыкант":
            option["label"] = "Музыкант и др."
    connection.execute(
        sa.text(
            "UPDATE application_questions SET options_json = CAST(:options AS jsonb) "
            "WHERE id = :question_id"
        ),
        {"options": json.dumps(options, ensure_ascii=False), "question_id": row["id"]},
    )
