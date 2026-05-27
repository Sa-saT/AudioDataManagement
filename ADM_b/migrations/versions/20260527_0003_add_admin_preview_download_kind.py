"""add admin_preview to download_kind enum

Revision ID: 20260527_0003
Revises: 20260526_0002
Create Date: 2026-05-27
"""
from alembic import op

revision = "0003_admin_preview_kind"
down_revision = "0002_drop_preview_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires COMMIT before ALTER TYPE when inside a transaction.
    op.execute("COMMIT")
    op.execute("ALTER TYPE download_kind ADD VALUE IF NOT EXISTS 'admin_preview'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op.
    pass
