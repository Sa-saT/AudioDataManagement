import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CreatorRank(str, enum.Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    platinum = "platinum"


class CreatorProfile(Base):
    __tablename__ = "creator_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[CreatorRank] = mapped_column(
        Enum(CreatorRank, name="creator_rank", native_enum=True),
        nullable=False,
        default=CreatorRank.bronze,
    )
    payout_method: Mapped[dict | None] = mapped_column(JSONB)

    user: Mapped["User"] = relationship("User", back_populates="creator_profile")
    audios: Mapped[list["Audio"]] = relationship("Audio", back_populates="creator")
