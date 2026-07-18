"""move automatic attachments into a questionnaire file question

Revision ID: 0009_file_question
Revises: 0008_question_branching
Create Date: 2026-07-18
"""

from alembic import op


revision = "0009_file_question"
down_revision = "0008_question_branching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO application_questions (
            code,
            text,
            help_text,
            answer_type,
            options_json,
            next_question_code,
            sort_order
        )
        SELECT
            'portfolio',
            'Добавьте примеры работ',
            NULL,
            'file',
            '[]'::jsonb,
            NULL,
            COALESCE(MAX(sort_order), 0) + 1
        FROM application_questions
        HAVING NOT EXISTS (
            SELECT 1 FROM application_questions WHERE answer_type = 'file'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM application_questions
        WHERE code = 'portfolio' AND answer_type = 'file'
        """
    )
