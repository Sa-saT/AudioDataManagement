import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import INET, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_uuid


class DownloadKind(str, enum.Enum):
    initial = "initial"
    redownload = "redownload"
    denied_no_token = "denied_no_token"
    denied_sold = "denied_sold"
    # creator (own audio) or admin: free, no sold, audio stays on Dashboard
    admin_preview = "admin_preview"


class DownloadLog(Base):
    __tablename__ = "download_logs"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id")
    )
    audio_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("audios.id"), nullable=False
    )
    kind: Mapped[DownloadKind] = mapped_column(
        Enum(DownloadKind, name="download_kind", native_enum=True), nullable=False
    )
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    audio_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("audios.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ActivityKind(str, enum.Enum):
    session = "session"
    order_view = "order_view"
    # 改訂2.4: DM スレッド (creator 単位) の既読マーカー
    dm_view = "dm_view"


# 統合活動ログ。session ping と order view を1テーブルで扱う (改訂2)。
# 将来の audio_view / search なども kind 追加で対応可能。
class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ActivityKind] = mapped_column(
        Enum(ActivityKind, name="activity_log_kind", native_enum=True, create_type=False),
        nullable=False,
    )
    # FK 制約は付けない (将来 audio_view / search 等を kind ごとに別テーブルに向けたいため)
    target_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
