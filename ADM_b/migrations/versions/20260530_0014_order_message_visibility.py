"""Add OrderMessage.visibility for admin↔creator private messages

ORDER_SPEC §15 (改訂2.3): user に見えない private channel を導入。
- public: 全参加者に見える (default、既存挙動)
- admin_creator: admin と creator (assigned / candidate) のみ閲覧可。user は不可視

Revision ID: 0014_order_message_visibility
Revises: 0013_orders_closed_at
Create Date: 2026-05-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0014_order_message_visibility"
down_revision = "0013_orders_closed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ENUM 新規作成 (Postgres は ALTER TYPE しか無いので新規定義)
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


def downgrade() -> None:
    op.drop_column("order_messages", "visibility")
    op.execute("DROP TYPE order_message_visibility")
