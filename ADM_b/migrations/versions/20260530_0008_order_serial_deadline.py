"""Add user_serial and desired_deadline to orders (改訂2)

Revision ID: 0008_order_serial_deadline
Revises: 0007_order_brief
Create Date: 2026-05-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_order_serial_deadline"
down_revision = "0007_order_brief"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("user_serial", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("desired_deadline", sa.Date(), nullable=True))

    # Backfill user_serial: per-user sequential numbering by created_at order
    op.execute(
        """
        WITH numbered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at) AS seq
            FROM orders
        )
        UPDATE orders o
           SET user_serial = numbered.seq
          FROM numbered
         WHERE o.id = numbered.id
        """
    )

    # Backfill desired_deadline = created_at + 7 days (date-only)
    op.execute(
        "UPDATE orders SET desired_deadline = (created_at + INTERVAL '7 days')::date "
        "WHERE desired_deadline IS NULL"
    )

    op.alter_column("orders", "user_serial", nullable=False)
    op.alter_column("orders", "desired_deadline", nullable=False)

    op.create_unique_constraint(
        "uq_orders_user_serial", "orders", ["user_id", "user_serial"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_orders_user_serial", "orders", type_="unique")
    op.drop_column("orders", "desired_deadline")
    op.drop_column("orders", "user_serial")
