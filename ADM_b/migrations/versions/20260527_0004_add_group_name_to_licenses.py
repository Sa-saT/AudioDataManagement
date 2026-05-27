"""add group_name to licenses

Revision ID: 0004_add_group_name
Revises: 0003_admin_preview_kind
Create Date: 2026-05-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_add_group_name"
down_revision = "0003_admin_preview_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("licenses", sa.Column("group_name", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("licenses", "group_name")
