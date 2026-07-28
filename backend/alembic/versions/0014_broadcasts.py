"""add scheduled broadcasts

Revision ID: 0014_broadcasts
Revises: 0013_support_tickets
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014_broadcasts"
down_revision: str | None = "0013_support_tickets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=32), nullable=False),
        sa.Column(
            "role_codes_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "disable_link_preview",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "target_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "sent_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "failed_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"]),
    )
    op.create_index(
        "ix_broadcasts_status_scheduled_at",
        "broadcasts",
        ["status", "scheduled_at"],
    )

    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("broadcast_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["broadcast_id"],
            ["broadcasts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("broadcast_id", "user_id"),
    )
    op.create_index(
        "ix_broadcast_recipients_pending",
        "broadcast_recipients",
        ["broadcast_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_broadcast_recipients_pending",
        table_name="broadcast_recipients",
    )
    op.drop_table("broadcast_recipients")
    op.drop_index("ix_broadcasts_status_scheduled_at", table_name="broadcasts")
    op.drop_table("broadcasts")
