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
    tags: list[str] = []
    favorite_count: int = 0
    is_favorited: bool = False


class AudioDetail(AudioListItem):
    description: str | None
    sample_rate: int
    bit_depth: int
    channels: int
    is_sold: bool
    is_public: bool
    downloaded_at: datetime | None
    created_at: datetime | None = None


class AudioUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    youtube_safe: bool | None = None
    is_public: bool | None = None
    tags: list[str] | None = None


class AudioListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[AudioListItem]


class DownloadResponse(BaseModel):
    download_url: str
    is_redownload: bool
    token_cost: int | None = None
    remaining_tokens: int | None = None
