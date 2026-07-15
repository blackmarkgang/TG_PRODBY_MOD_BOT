"""add topic role permissions

Revision ID: 0003_topic_roles
Revises: 0002_file_metadata
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_topic_roles"
down_revision = "0002_file_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_role_permissions",
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["community_roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["forum_topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("topic_id", "role_id"),
    )


def downgrade() -> None:
    op.drop_table("topic_role_permissions")
