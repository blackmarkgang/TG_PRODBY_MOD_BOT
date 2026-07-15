"""add application file metadata

Revision ID: 0002_file_metadata
Revises: 0001_initial
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_file_metadata"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("application_files", sa.Column("file_name", sa.String(length=255), nullable=True))
    op.add_column("application_files", sa.Column("mime_type", sa.String(length=128), nullable=True))
    op.add_column("application_files", sa.Column("file_size", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("application_files", "file_size")
    op.drop_column("application_files", "mime_type")
    op.drop_column("application_files", "file_name")
