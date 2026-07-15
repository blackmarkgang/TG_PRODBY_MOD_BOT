"""add dynamic questionnaire

Revision ID: 0005_questionnaire
Revises: 0004_user_bans
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_questionnaire"
down_revision = "0004_user_bans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "answer_labels_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    questions = op.create_table(
        "application_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("text", sa.String(length=512), nullable=False),
        sa.Column("help_text", sa.Text(), nullable=True),
        sa.Column("answer_type", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.bulk_insert(
        questions,
        [
            {
                "code": "age",
                "text": "Сколько вам лет?",
                "help_text": "Отправьте возраст одним числом.",
                "answer_type": "number",
                "sort_order": 1,
            },
            {
                "code": "role_details",
                "text": "Расскажите о себе",
                "help_text": "Чем вы занимаетесь в музыке или смежных направлениях? Чем полезны сообществу?",
                "answer_type": "text",
                "sort_order": 2,
            },
            {
                "code": "motivation",
                "text": "Почему вы хотите попасть в Prod.by?",
                "help_text": "Напишите коротко и своими словами.",
                "answer_type": "text",
                "sort_order": 3,
            },
            {
                "code": "expectations",
                "text": "Что вы ожидаете от участия?",
                "help_text": "Расскажите, что хотите получить от сообщества и чем готовы делиться.",
                "answer_type": "text",
                "sort_order": 4,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("application_questions")
    op.drop_column("applications", "answer_labels_json")
