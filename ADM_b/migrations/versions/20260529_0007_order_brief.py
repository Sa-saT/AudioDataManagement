"""Add brief JSONB column to orders for structured hearing data

Revision ID: 0007_order_brief
Revises: 0006_nullable_audio_id
Create Date: 2026-05-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_order_brief"
down_revision = "0006_nullable_audio_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("brief", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "brief")
