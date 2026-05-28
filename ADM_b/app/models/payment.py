import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid
from app.models.creator import CreatorRank


class PayoutStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class CreatorRankPrice(Base):
    __tablename__ = "creator_rank_prices"
    __table_args__ = (
        CheckConstraint("unit_price_yen >= 0", name="unit_price_yen_nonneg"),
    )

    rank: Mapped[CreatorRank] = mapped_column(
        Enum(CreatorRank, name="creator_rank", native_enum=True, create_type=False),
        primary_key=True,
    )
    unit_price_yen: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CreatorPayout(Base):
    __tablename__ = "creator_payouts"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    audio_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("audios.id"), unique=True, nullable=True
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("creator_profiles.user_id"), nullable=False
    )
    rank_at_payout: Mapped[CreatorRank] = mapped_column(
        Enum(CreatorRank, name="creator_rank", native_enum=True, create_type=False),
        nullable=False,
    )
    unit_price_yen: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_yen: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus, name="payout_status", native_enum=True),
        nullable=False,
        default=PayoutStatus.pending,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TokenConsumption(Base):
    __tablename__ = "token_consumptions"
    __table_args__ = (
        CheckConstraint("tokens > 0", name="tokens_positive"),
        Index("idx_tc_user_period", "user_id", "period_yyyymm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    audio_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("audios.id"), nullable=True
    )
    license_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("licenses.id"), nullable=False
    )
    tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    period_yyyymm: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TokenGrant(Base):
    __tablename__ = "token_grants"
    __table_args__ = (
        CheckConstraint("tokens > 0", name="tokens_positive"),
        Index("idx_tg_user_period", "user_id", "period_yyyymm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    granted_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    period_yyyymm: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
