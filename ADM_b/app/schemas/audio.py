from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreatorBrief(BaseModel):
    id: str
    display_name: str


class AudioListItem(BaseModel):
    id: str
    title: str
    creator: CreatorBrief
    duration_sec: int
    token_cost: int
    peaks: list[Any]
    youtube_safe: bool
    published_at: datetime | None


class AudioDetail(AudioListItem):
    description: str | None
    sample_rate: int
    bit_depth: int
    channels: int
    is_sold: bool
    downloaded_at: datetime | None


class AudioListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[AudioListItem]
