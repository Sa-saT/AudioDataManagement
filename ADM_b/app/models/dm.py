"""DM (Direct Message) - admin↔creator の継続的やりとり。DM_SPEC 参照。"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid


class DMSenderKind(str, enum.Enum):
    admin = "admin"
    creator = "creator"


class DirectMessage(Base):
    __tablename__ = "direct_messages"
    __table_args__ = (
        CheckConstraint("char_length(content) <= 4000", name="ck_dm_content_len"),
        Index("idx_dm_creator_created", "creator_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    # スレッドを一意に識別する creator のユーザ ID (admin は全員チーム扱い)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    sender_kind: Mapped[DMSenderKind] = mapped_column(
        Enum(DMSenderKind, name="dm_sender_kind", native_enum=True, create_type=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id])  # type: ignore[name-defined]
    sender: Mapped["User | None"] = relationship("User", foreign_keys=[sender_id])  # type: ignore[name-defined]
