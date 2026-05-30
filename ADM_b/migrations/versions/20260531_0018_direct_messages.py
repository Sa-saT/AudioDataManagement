"""Create direct_messages + extend activity_log_kind with dm_view (改訂2.4)

DM_SPEC §3:
admin↔creator の継続的やりとり。Order と独立。admin はチーム扱いで
全 admin が全 creator との DM を共有 (sender_kind で区別)。

Revision ID: 0018_direct_messages
Revises: 0017_order_memos
Create Date: 2026-05-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID as PgUUID

revision = "0018_direct_messages"
down_revision = "0017_order_memos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # activity_log_kind に dm_view を追加
    op.execute("ALTER TYPE activity_log_kind ADD VALUE IF NOT EXISTS 'dm_view'")

    dm_sender_kind = ENUM("admin", "creator", name="dm_sender_kind", create_type=False)
    dm_sender_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "direct_messages",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("creator_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_kind", dm_sender_kind, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("attachment_path", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("char_length(content) <= 4000", name="ck_dm_content_len"),
    )
    op.create_index("idx_dm_creator_created", "direct_messages", ["creator_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_dm_creator_created", table_name="direct_messages")
    op.drop_table("direct_messages")
    op.execute("DROP TYPE dm_sender_kind")
    # ENUM の値削除は PostgreSQL では非対応 (型を作り直すしかない)。ここでは省略。
