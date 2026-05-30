"""Create order_memos table (改訂2.4: Order 共有メモ)

ORDER_SPEC §16.2:
1 Order に admin 枠 / creator 枠 各1つ。assigned creator と admin のみ
閲覧・編集可。user は完全不可視。close/cancel 後は read-only (アプリ層で制御)。

Revision ID: 0017_order_memos
Revises: 0016_drop_message_visibility
Create Date: 2026-05-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID as PgUUID

revision = "0017_order_memos"
down_revision = "0016_drop_message_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    memo_author_kind = ENUM("admin", "creator", name="memo_author_kind", create_type=False)
    memo_author_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "order_memos",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_kind", memo_author_kind, nullable=False),
        sa.Column("author_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("order_id", "author_kind", name="uq_order_memos_order_kind"),
        sa.CheckConstraint("char_length(content) <= 2000", name="ck_order_memos_content_len"),
    )


def downgrade() -> None:
    op.drop_table("order_memos")
    op.execute("DROP TYPE memo_author_kind")
