"""Add multi-slot SE submission support (9-A5)

ORDER_SPEC §9.1 9-A5: SE は複数バリエーション納品対応。
- order_messages に attachment_paths (JSONB, nullable): SE 複数スロットのファイルパス配列
- order_messages に attachment_peaks_list (JSONB, nullable): 各スロットの peaks v2 配列

既存レコードはそのまま (attachment_path / attachment_peaks が単一ファイルを参照し続ける)。

Revision ID: 0020_se_multi_slot
Revises: 0019_submission_versions
Create Date: 2026-06-01
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0020_se_multi_slot"
down_revision = "0019_submission_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_messages", sa.Column("attachment_paths", JSONB, nullable=True))
    op.add_column("order_messages", sa.Column("attachment_peaks_list", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("order_messages", "attachment_peaks_list")
    op.drop_column("order_messages", "attachment_paths")
