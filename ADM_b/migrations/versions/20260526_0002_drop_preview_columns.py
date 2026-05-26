"""drop preview_path and preview_duration_sec from audios

Revision ID: 0002_drop_preview_columns
Revises: 0001_initial
Create Date: 2026-05-26

動的チャンク切り出し方式に変更したため、事前生成プレビューファイル関連の列を削除。
視聴は GET /audios/{id}/stream?start=N で原本から 10 秒をその都度切り出す。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_drop_preview_columns"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_audios_preview_duration_sec_range", "audios", type_="check")
    op.drop_column("audios", "preview_path")
    op.drop_column("audios", "preview_duration_sec")


def downgrade() -> None:
    op.add_column(
        "audios",
        sa.Column("preview_duration_sec", sa.Integer(), nullable=True, server_default="10"),
    )
    op.add_column(
        "audios",
        sa.Column("preview_path", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_audios_preview_duration_sec_range",
        "audios",
        "preview_duration_sec > 0 AND preview_duration_sec <= 60",
    )
