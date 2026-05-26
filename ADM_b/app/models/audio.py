import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Audio(Base, TimestampMixin):
    __tablename__ = "audios"
    __table_args__ = (
        CheckConstraint("duration_sec > 0", name="duration_sec_positive"),
        CheckConstraint(
            "preview_duration_sec > 0 AND preview_duration_sec <= 60",
            name="preview_duration_sec_range",
        ),
        Index("idx_audios_published_at", "published_at"),
        Index("idx_audios_recommend_score", "recommend_score"),
        Index("idx_audios_creator_id", "creator_id"),
        Index(
            "idx_audios_available",
            "published_at",
            postgresql_where=text("downloaded_by_user_id IS NULL AND is_public = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("creator_profiles.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    preview_path: Mapped[str] = mapped_column(Text, nullable=False)
    preview_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    bit_depth: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    channels: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    peaks: Mapped[list] = mapped_column(JSONB, nullable=False)

    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    youtube_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recommend_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    downloaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), unique=True
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creator: Mapped["CreatorProfile"] = relationship("CreatorProfile", back_populates="audios")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class AudioTag(Base):
    __tablename__ = "audio_tags"

    audio_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("audios.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
