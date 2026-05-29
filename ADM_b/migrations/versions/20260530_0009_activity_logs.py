"""Add activity_logs table for session ping / order view tracking

Revision ID: 0009_activity_logs
Revises: 0008_order_serial_deadline
Create Date: 2026-05-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_activity_logs"
down_revision = "0008_order_serial_deadline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum("session", "order_view", name="activity_log_kind"),
            nullable=False,
        ),
        # target_id は FK 制約なし (将来 kind ごとに異なる対象を持つ)
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_activity_logs_user_kind_created",
        "activity_logs",
        ["user_id", "kind", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_activity_logs_target_kind_created",
        "activity_logs",
        ["target_id", "kind", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_activity_logs_target_kind_created", table_name="activity_logs")
    op.drop_index("ix_activity_logs_user_kind_created", table_name="activity_logs")
    op.drop_table("activity_logs")
    sa.Enum(name="activity_log_kind").drop(op.get_bind(), checkfirst=True)
