"""add user bans

Revision ID: 0004_user_bans
Revises: 0003_topic_roles
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_user_bans"
down_revision = "0003_topic_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_banned", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "banned_at")
    op.drop_column("users", "is_banned")
