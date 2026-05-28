"""add commission tables (system_settings, orders, order_candidates, order_messages)

Revision ID: 0005_commission
Revises: 0004_add_group_name
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_commission"
down_revision = "0004_add_group_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "updated_by_admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute(
        "INSERT INTO system_settings (key, value, description) VALUES "
        "('commission_enabled', 'false', '発注 (Commission) 機能の有効/無効')"
    )

    op.execute(
        "CREATE TYPE order_status AS ENUM "
        "('draft','open','recruiting','assigned','reviewing','done','cancelled')"
    )
    op.execute(
        "CREATE TYPE candidate_response_status AS ENUM ('pending','accepted','declined')"
    )
    op.execute(
        "CREATE TYPE order_message_kind AS ENUM "
        "('comment','status_change','submission','rejection','done')"
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "token_cost",
            sa.Integer(),
            nullable=False,
            comment="user-specified token amount",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="order_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "assigned_creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creator_profiles.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_by_admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column(
            "done_by_admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("done_at", sa.DateTime(timezone=True)),
        sa.Column("file_path", sa.Text()),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("token_cost > 0", name="ck_orders_token_cost_positive"),
    )

    op.create_table(
        "order_candidate_creators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creator_profiles.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sent_by_admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "response_status",
            postgresql.ENUM(name="candidate_response_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("response_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("order_id", "creator_id", name="uq_order_candidate"),
    )

    op.create_table(
        "order_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text()),
        sa.Column("attachment_path", sa.Text()),
        sa.Column(
            "kind",
            postgresql.ENUM(name="order_message_kind", create_type=False),
            nullable=False,
            server_default="comment",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("order_messages")
    op.drop_table("order_candidate_creators")
    op.drop_table("orders")
    op.drop_table("system_settings")
    op.execute("DROP TYPE IF EXISTS order_message_kind")
    op.execute("DROP TYPE IF EXISTS candidate_response_status")
    op.execute("DROP TYPE IF EXISTS order_status")
