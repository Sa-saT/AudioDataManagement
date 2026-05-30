"""Add Order.submission_peaks for WaveformPlayer preview of submission file

NOTIFICATION_SPEC / ORDER_SPEC §9.1 9-A11:
creator が提出した submission ファイル (storage/orders/submissions/{id}.wav) に対して
peaks v2 ({n, max, min, rms}) を生成し DB に保持。フロントの WaveformPlayer で
シェーダ描画する際に使用する。

Revision ID: 0015_order_submission_peaks
Revises: 0014_order_message_visibility
Create Date: 2026-05-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_order_submission_peaks"
down_revision = "0014_order_message_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("submission_peaks", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "submission_peaks")
