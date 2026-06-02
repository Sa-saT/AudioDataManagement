"""Drop wrong UNIQUE on audios.downloaded_by_user_id

初期マイグレーション (0001) で `downloaded_by_user_id` に UNIQUE が誤って
設定されていた。これにより「1 ユーザは生涯 1 音源しか購入できない」状態に。

仕様 (単発販売):
- 1 音源 = 1 購入者 (これは audios の各行で 0 or 1 user)
- 1 ユーザ = 任意数の音源を購入可能
→ `downloaded_by_user_id` は **UNIQUE であってはならない**

Revision ID: 0024_drop_unique_buyer
Revises: 0023_license_session_id
Create Date: 2026-06-02
"""
from alembic import op

revision = "0024_drop_unique_buyer"
down_revision = "0023_license_session_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 制約名は initial migration で自動生成された pg 既定名 "uq_audios_downloaded_by_user_id"
    op.drop_constraint("uq_audios_downloaded_by_user_id", "audios", type_="unique")
    # 単発販売の高速検索用 partial index は既に存在 (idx_audios_available) なので追加不要


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_audios_downloaded_by_user_id",
        "audios",
        ["downloaded_by_user_id"],
    )
