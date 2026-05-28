"""Make audio_id nullable on creator_payouts and token_consumptions (for commission orders)

Revision ID: 20260528_0006
Revises: 20260528_0005
Create Date: 2026-05-28
"""
from alembic import op

revision = "0006_nullable_audio_id"
down_revision = "0005_commission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("creator_payouts", "audio_id", nullable=True)
    op.alter_column("token_consumptions", "audio_id", nullable=True)


def downgrade() -> None:
    op.alter_column("token_consumptions", "audio_id", nullable=False)
    op.alter_column("creator_payouts", "audio_id", nullable=False)
