"""Drop OrderMessage.visibility (改訂2.4 で私信機能を廃止)

ORDER_SPEC §16.3: admin↔creator 私信は order_memos + direct_messages に分離。
- visibility = 'admin_creator' のレコードを物理削除
- visibility カラムを drop
- ENUM 型を drop

Revision ID: 0016_drop_message_visibility
Revises: 0015_order_submission_peaks
Create Date: 2026-05-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0016_drop_message_visibility"
down_revision = "0015_order_submission_peaks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. admin_creator 私信を物理削除
    op.execute("DELETE FROM order_messages WHERE visibility = 'admin_creator'")
    # 2. カラム drop
    op.drop_column("order_messages", "visibility")
    # 3. ENUM 型 drop
    op.execute("DROP TYPE order_message_visibility")


def downgrade() -> None:
    op.execute("CREATE TYPE order_message_visibility AS ENUM ('public', 'admin_creator')")
    op.add_column(
        "order_messages",
        sa.Column(
            "visibility",
            sa.Enum("public", "admin_creator",
                    name="order_message_visibility",
                    native_enum=True,
                    create_type=False),
            nullable=False,
            server_default="public",
        ),
    )
