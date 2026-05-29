"""order_brief_edits table + brief_edit enum value (改訂2.1)

ORDER_SPEC.md §13: 発注後ブリーフ編集 (diff 記録 + bot 通知)

Revision ID: 0012_order_brief_edits
Revises: 0011_peaks_v2_backfill
Create Date: 2026-05-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_order_brief_edits"
down_revision = "0011_peaks_v2_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE は transaction 外で実行する必要がある
    op.execute("COMMIT")
    op.execute("ALTER TYPE order_message_kind ADD VALUE IF NOT EXISTS 'brief_edit'")

    op.create_table(
        "order_brief_edits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # editor は user 削除時に NULL に (履歴は残す)
        sa.Column(
            "editor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field_path", sa.Text(), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_order_brief_edits_order_field_time",
        "order_brief_edits",
        ["order_id", "field_path", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_order_brief_edits_order_field_time", table_name="order_brief_edits")
    op.drop_table("order_brief_edits")
    # Postgres は enum 値の削除を直接サポートしないため brief_edit は残す
