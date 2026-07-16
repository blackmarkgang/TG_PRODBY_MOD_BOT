"""add editable bot text settings

Revision ID: 0007_bot_text_settings
Revises: 0006_admin_profiles
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_bot_text_settings"
down_revision = "0006_admin_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_text_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("bot_text_settings")
