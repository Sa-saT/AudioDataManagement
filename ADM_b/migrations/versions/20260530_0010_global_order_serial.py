"""Switch orders.user_serial to global serial backed by a sequence

改訂2 改修: per-user → 全 Commission Order 通し番号。
キャンセル/削除された番号は再利用しない (sequence の単調増加で担保)。

Revision ID: 0010_global_order_serial
Revises: 0009_activity_logs
Create Date: 2026-05-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0010_global_order_serial"
down_revision = "0009_activity_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 既存の per-user 制約を外す
    op.drop_constraint("uq_orders_user_serial", "orders", type_="unique")

    # 2) カラム名 user_serial → serial
    op.alter_column("orders", "user_serial", new_column_name="serial")

    # 3) global 通し番号で再付番 (created_at 昇順)
    op.execute(
        """
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_serial
              FROM orders
        )
        UPDATE orders o
           SET serial = numbered.new_serial
          FROM numbered
         WHERE o.id = numbered.id
        """
    )

    # 4) sequence 作成 + 既存 MAX に合わせて初期化
    op.execute("CREATE SEQUENCE orders_serial_seq AS BIGINT START WITH 1 INCREMENT BY 1")
    op.execute(
        "SELECT setval('orders_serial_seq', "
        "COALESCE((SELECT MAX(serial) FROM orders), 0) + 1, false)"
    )
    op.execute("ALTER SEQUENCE orders_serial_seq OWNED BY orders.serial")

    # 5) default = nextval(...) でアプリ側の挿入が自動採番されるようにする
    op.alter_column(
        "orders",
        "serial",
        server_default=sa.text("nextval('orders_serial_seq')"),
    )

    # 6) 全体一意性 (cancel された番号も占有したまま残る)
    op.create_unique_constraint("uq_orders_serial", "orders", ["serial"])


def downgrade() -> None:
    op.drop_constraint("uq_orders_serial", "orders", type_="unique")
    op.alter_column("orders", "serial", server_default=None)
    op.execute("DROP SEQUENCE IF EXISTS orders_serial_seq")
    op.alter_column("orders", "serial", new_column_name="user_serial")
    # NOTE: per-user 連番への復元 backfill は行わない (lossy)
    op.create_unique_constraint("uq_orders_user_serial", "orders", ["user_id", "user_serial"])
