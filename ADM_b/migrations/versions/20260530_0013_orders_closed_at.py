"""Add orders.closed_at for archive (user 受け取る)

ORDER_SPEC §14 (改訂2.2): user が done 後に「受け取る」を押すと closed_at がセットされ、
user/creator の一覧から非表示 (admin の archive タブのみ参照可能) になる。

Revision ID: 0013_orders_closed_at
Revises: 0012_order_brief_edits
Create Date: 2026-05-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0013_orders_closed_at"
down_revision = "0012_order_brief_edits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_orders_closed_at", "orders", ["closed_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_closed_at", table_name="orders")
    op.drop_column("orders", "closed_at")
