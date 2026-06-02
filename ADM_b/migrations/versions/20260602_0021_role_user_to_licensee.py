"""Rename user_role enum value 'user' -> 'licensee'

ロール命名整理 (2026-06-02): 客ロール `user` を `licensee` に改名する。
`.lic` ファイル仕様 (licensor=creator / licensee=客) との意味的一貫性が目的。
旧 `role=user` の lic ファイルは security/license.py の validate_payload() で
互換正規化されるため、既存 lic は引き続き利用可能。

PostgreSQL の ENUM RENAME VALUE は単方向。downgrade で元に戻せる。

Revision ID: 0021_rename_user_role_to_licensee
Revises: 0020_se_multi_slot
Create Date: 2026-06-02
"""
from alembic import op

revision = "0021_role_user_to_licensee"
down_revision = "0020_se_multi_slot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role RENAME VALUE 'user' TO 'licensee'")


def downgrade() -> None:
    op.execute("ALTER TYPE user_role RENAME VALUE 'licensee' TO 'user'")
