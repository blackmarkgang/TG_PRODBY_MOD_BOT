"""add admin profile fields

Revision ID: 0006_admin_profiles
Revises: 0005_questionnaire
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_admin_profiles"
down_revision = "0005_questionnaire"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_users", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column("admin_users", sa.Column("first_name", sa.String(length=128), nullable=True))
    op.add_column("admin_users", sa.Column("last_name", sa.String(length=128), nullable=True))
    op.execute(
        """
        UPDATE admin_users AS admin
        SET username = users.username,
            first_name = users.first_name,
            last_name = users.last_name
        FROM users
        WHERE users.telegram_id = admin.telegram_id
        """
    )


def downgrade() -> None:
    op.drop_column("admin_users", "last_name")
    op.drop_column("admin_users", "first_name")
    op.drop_column("admin_users", "username")
