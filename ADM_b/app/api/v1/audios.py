import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Audio, CreatorProfile
from app.schemas.audio import AudioDetail, AudioListItem, AudioListResponse, CreatorBrief

router = APIRouter(prefix="/audios", tags=["audios"])

_ALLOWED_PER_PAGE = {25, 50, 100, 200}


def _to_list_item(audio: Audio) -> AudioListItem:
    return AudioListItem(
        id=str(audio.id),
        title=audio.title,
        creator=CreatorBrief(
            id=str(audio.creator.user_id),
            display_name=audio.creator.display_name,
        ),
        duration_sec=audio.duration_sec,
        token_cost=audio.duration_sec,
        peaks=audio.peaks,
        youtube_safe=audio.youtube_safe,
        published_at=audio.published_at,
    )


@router.get("", response_model=AudioListResponse)
def list_audios(
    sort: Literal["recommended", "newest"] = Query("recommended"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50),
    db: Session = Depends(get_db),
) -> AudioListResponse:
    if per_page not in _ALLOWED_PER_PAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PER_PAGE", "message": f"per_page must be one of {sorted(_ALLOWED_PER_PAGE)}"},
        )

    base = (
        select(Audio)
        .options(joinedload(Audio.creator))
        .where(Audio.is_public.is_(True), Audio.downloaded_by_user_id.is_(None))
    )

    total: int = db.execute(
        select(func.count()).select_from(
            base.subquery()
        )
    ).scalar_one()

    order = Audio.recommend_score.desc() if sort == "recommended" else Audio.published_at.desc()
    rows = db.execute(
        base.order_by(order).offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()

    return AudioListResponse(
        total=total,
        page=page,
        per_page=per_page,
        items=[_to_list_item(a) for a in rows],
    )


@router.get("/{audio_id}", response_model=AudioDetail)
def get_audio(audio_id: str, db: Session = Depends(get_db)) -> AudioDetail:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    audio = db.execute(
        select(Audio)
        .options(joinedload(Audio.creator))
        .where(Audio.id == parsed_id, Audio.is_public.is_(True))
    ).scalar_one_or_none()

    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    return AudioDetail(
        id=str(audio.id),
        title=audio.title,
        creator=CreatorBrief(
            id=str(audio.creator.user_id),
            display_name=audio.creator.display_name,
        ),
        duration_sec=audio.duration_sec,
        token_cost=audio.duration_sec,
        peaks=audio.peaks,
        youtube_safe=audio.youtube_safe,
        published_at=audio.published_at,
        description=audio.description,
        sample_rate=audio.sample_rate,
        bit_depth=audio.bit_depth,
        channels=audio.channels,
        is_sold=audio.downloaded_by_user_id is not None,
        downloaded_at=audio.downloaded_at,
    )
