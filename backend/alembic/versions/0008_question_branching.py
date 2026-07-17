"""add questionnaire choices and branching

Revision ID: 0008_question_branching
Revises: 0007_bot_text_settings
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_question_branching"
down_revision = "0007_bot_text_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "application_questions",
        sa.Column(
            "options_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "application_questions",
        sa.Column("next_question_code", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application_questions", "next_question_code")
    op.drop_column("application_questions", "options_json")
