"""Add licenses.current_session_id for single-session enforcement (B案)

ライセンス毎に「現在有効なセッション」を 1 つだけ持つ。
- /auth/activate 毎に新しい UUID を発行し、DB に上書き保存
- JWT の `sid` claim と DB の current_session_id を照合
- 不一致 → 401 SESSION_INVALIDATED (旧セッションは強制ログアウト)

これにより lic ファイルをコピーして配布されても、後から activate された
端末だけが有効となり、先に activate していた端末は自動ログアウトされる
(Spotify モデル)。

Revision ID: 0023_license_session_id
Revises: 0022_admin_config_seeds
Create Date: 2026-06-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0023_license_session_id"
down_revision = "0022_admin_config_seeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "licenses",
        sa.Column("current_session_id", PgUUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("licenses", "current_session_id")
