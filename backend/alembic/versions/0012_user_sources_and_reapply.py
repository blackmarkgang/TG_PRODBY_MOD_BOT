"""track user sources and allow annulled applications to be resubmitted

Revision ID: 0012_user_sources_reapply
Revises: 0011_split_musicians
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_user_sources_reapply"
down_revision = "0011_split_musicians"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_group_member",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "has_used_bot",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "can_reapply",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE users
        SET has_used_bot = true
        WHERE EXISTS (
            SELECT 1 FROM applications WHERE applications.user_id = users.id
        )
        """
    )
    op.execute(
        """
        INSERT INTO community_roles (code, title)
        VALUES ('creative_production', 'Креативный продакшн')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM user_roles
        WHERE role_id = (
            SELECT id FROM community_roles WHERE code = 'creative_production'
        )
        """
    )
    op.execute("DELETE FROM community_roles WHERE code = 'creative_production'")
    op.drop_column("users", "can_reapply")
    op.drop_column("users", "has_used_bot")
    op.drop_column("users", "is_group_member")
