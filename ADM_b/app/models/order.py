import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid


class OrderStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    recruiting = "recruiting"
    assigned = "assigned"
    reviewing = "reviewing"
    done = "done"
    cancelled = "cancelled"


class CandidateResponseStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class OrderMessageKind(str, enum.Enum):
    comment = "comment"
    status_change = "status_change"
    submission = "submission"
    rejection = "rejection"
    done = "done"
    # 改訂2.1: 発注後ブリーフ編集の bot 通知
    brief_edit = "brief_edit"


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("token_cost > 0", name="ck_orders_token_cost_positive"),
        UniqueConstraint("serial", name="uq_orders_serial"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # 改訂2 (改修): Commission Order 全体の通し番号。sequence で採番、cancel しても再利用しない
    serial: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    brief: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    # 改訂2: 希望締切日 (default = created_at + 7日)
    desired_deadline: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", native_enum=True, create_type=False),
        nullable=False,
        default=OrderStatus.draft,
    )
    assigned_creator_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("creator_profiles.user_id", ondelete="SET NULL")
    )
    assigned_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 改訂2.2: user が「受け取る」を押すと設定される。user/creator の一覧から非表示にする目印
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_path: Mapped[str | None] = mapped_column(Text)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # type: ignore[name-defined]
    assigned_creator: Mapped["CreatorProfile | None"] = relationship(  # type: ignore[name-defined]
        "CreatorProfile", foreign_keys=[assigned_creator_id]
    )
    candidates: Mapped[list["OrderCandidateCreator"]] = relationship(
        "OrderCandidateCreator", back_populates="order", cascade="all, delete-orphan"
    )
    messages: Mapped[list["OrderMessage"]] = relationship(
        "OrderMessage", back_populates="order", cascade="all, delete-orphan",
        order_by="OrderMessage.created_at"
    )


class OrderCandidateCreator(Base):
    __tablename__ = "order_candidate_creators"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("creator_profiles.user_id", ondelete="CASCADE"), nullable=False
    )
    sent_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    response_status: Mapped[CandidateResponseStatus] = mapped_column(
        Enum(CandidateResponseStatus, name="candidate_response_status", native_enum=True, create_type=False),
        nullable=False,
        default=CandidateResponseStatus.pending,
    )
    response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped["Order"] = relationship("Order", back_populates="candidates")
    creator: Mapped["CreatorProfile"] = relationship("CreatorProfile", foreign_keys=[creator_id])  # type: ignore[name-defined]


class OrderMessage(Base):
    __tablename__ = "order_messages"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    content: Mapped[str | None] = mapped_column(Text)
    attachment_path: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[OrderMessageKind] = mapped_column(
        Enum(OrderMessageKind, name="order_message_kind", native_enum=True, create_type=False),
        nullable=False,
        default=OrderMessageKind.comment,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped["Order"] = relationship("Order", back_populates="messages")
    sender: Mapped["User | None"] = relationship("User", foreign_keys=[sender_id])  # type: ignore[name-defined]


# 改訂2.1: ブリーフ事後編集の差分履歴。1 field 1 行で記録する。
# 同一 PATCH 内で複数 field が変わった場合は、同時刻でレコードが N 行作られる。
class OrderBriefEdit(Base):
    __tablename__ = "order_brief_edits"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    editor_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # brief の field 名 (例: "emotions_target", "length_sec", "bgm_scenes")
    field_path: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped["Order"] = relationship("Order", foreign_keys=[order_id])
    editor: Mapped["User | None"] = relationship("User", foreign_keys=[editor_id])  # type: ignore[name-defined]
