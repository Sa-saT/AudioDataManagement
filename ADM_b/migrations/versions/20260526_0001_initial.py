"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def _enum_ref(name: str) -> postgresql.ENUM:
    """Reference an existing ENUM type without re-emitting CREATE TYPE."""
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'creator', 'admin')")
    op.execute("CREATE TYPE creator_rank AS ENUM ('bronze', 'silver', 'gold', 'platinum')")
    op.execute("CREATE TYPE payout_status AS ENUM ('pending', 'paid', 'cancelled')")
    op.execute(
        "CREATE TYPE download_kind AS ENUM "
        "('initial', 'redownload', 'denied_no_token', 'denied_sold')"
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("email", sa.Text(), unique=True),
        sa.Column("role", _enum_ref("user_role"), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "licenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("license_code", sa.Text(), nullable=False, unique=True),
        sa.Column("role", _enum_ref("user_role"), nullable=False),
        sa.Column("monthly_quota_tokens", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text()),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("monthly_quota_tokens >= 0", name="ck_licenses_monthly_quota_nonneg"),
    )

    op.create_table(
        "creator_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("bio", sa.Text()),
        sa.Column("rank", _enum_ref("creator_rank"), nullable=False, server_default="bronze"),
        sa.Column("payout_method", postgresql.JSONB()),
    )

    op.create_table(
        "audios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creator_profiles.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("preview_path", sa.Text(), nullable=False),
        sa.Column("preview_duration_sec", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("bit_depth", sa.SmallInteger(), nullable=False),
        sa.Column("channels", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column("peaks", postgresql.JSONB(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("youtube_safe", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("recommend_score", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "downloaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            unique=True,
        ),
        sa.Column("downloaded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("duration_sec > 0", name="ck_audios_duration_sec_positive"),
        sa.CheckConstraint(
            "preview_duration_sec > 0 AND preview_duration_sec <= 60",
            name="ck_audios_preview_duration_sec_range",
        ),
    )
    op.create_index("idx_audios_published_at", "audios", ["published_at"])
    op.create_index("idx_audios_recommend_score", "audios", ["recommend_score"])
    op.create_index("idx_audios_creator_id", "audios", ["creator_id"])
    op.create_index(
        "idx_audios_available",
        "audios",
        ["published_at"],
        postgresql_where=sa.text("downloaded_by_user_id IS NULL AND is_public = true"),
    )

    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
    )

    op.create_table(
        "audio_tags",
        sa.Column(
            "audio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "creator_rank_prices",
        sa.Column("rank", _enum_ref("creator_rank"), primary_key=True),
        sa.Column("unit_price_yen", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("unit_price_yen >= 0", name="ck_creator_rank_prices_unit_price_yen_nonneg"),
    )
    op.execute(
        "INSERT INTO creator_rank_prices (rank, unit_price_yen) VALUES "
        "('bronze', 100), ('silver', 200), ('gold', 400), ('platinum', 800)"
    )

    op.create_table(
        "creator_payouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audios.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("creator_profiles.user_id"),
            nullable=False,
        ),
        sa.Column("rank_at_payout", _enum_ref("creator_rank"), nullable=False),
        sa.Column("unit_price_yen", sa.Integer(), nullable=False),
        sa.Column("amount_yen", sa.Integer(), nullable=False),
        sa.Column("status", _enum_ref("payout_status"), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("paid_by_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "token_consumptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("audio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("audios.id"), nullable=False),
        sa.Column("license_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("licenses.id"), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("period_yyyymm", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tokens > 0", name="ck_token_consumptions_tokens_positive"),
    )
    op.create_index("idx_tc_user_period", "token_consumptions", ["user_id", "period_yyyymm"])

    op.create_table(
        "token_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "granted_by_admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("period_yyyymm", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tokens > 0", name="ck_token_grants_tokens_positive"),
    )
    op.create_index("idx_tg_user_period", "token_grants", ["user_id", "period_yyyymm"])

    op.create_table(
        "favorites",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "audio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "download_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("audio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("audios.id"), nullable=False),
        sa.Column("kind", _enum_ref("download_kind"), nullable=False),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("download_logs")
    op.drop_table("favorites")
    op.drop_index("idx_tg_user_period", table_name="token_grants")
    op.drop_table("token_grants")
    op.drop_index("idx_tc_user_period", table_name="token_consumptions")
    op.drop_table("token_consumptions")
    op.drop_table("creator_payouts")
    op.drop_table("creator_rank_prices")
    op.drop_table("audio_tags")
    op.drop_table("tags")
    op.drop_index("idx_audios_available", table_name="audios")
    op.drop_index("idx_audios_creator_id", table_name="audios")
    op.drop_index("idx_audios_recommend_score", table_name="audios")
    op.drop_index("idx_audios_published_at", table_name="audios")
    op.drop_table("audios")
    op.drop_table("creator_profiles")
    op.drop_table("licenses")
    op.drop_table("users")
    op.execute("DROP TYPE download_kind")
    op.execute("DROP TYPE payout_status")
    op.execute("DROP TYPE creator_rank")
    op.execute("DROP TYPE user_role")
