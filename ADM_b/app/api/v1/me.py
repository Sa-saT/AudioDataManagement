import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    ActivityKind,
    ActivityLog,
    Audio,
    DownloadKind,
    DownloadLog,
    TokenConsumption,
)
from app.models.audio import AudioTag, Tag
from app.schemas.audio import CreatorBrief
from app.security.deps import get_current_user
from app.security.signed_url import (
    SignedURLError,
    issue_copy_download,
    verify_copy_download,
)
from app.services import audio_file

# 直近この秒数以内に同ユーザの session 記録があれば新規 INSERT しない
SESSION_DEDUP_WINDOW_SEC = 30 * 60  # 30分

router = APIRouter(prefix="/me", tags=["me"])


class MyDownloadItem(BaseModel):
    id: str
    title: str
    creator: CreatorBrief
    duration_sec: int
    token_cost: int
    tags: list[str] = []
    # v1: list[float] / v2: {"n","max","min","rms"} — 改訂2 で v2 に統一
    peaks: list[Any] | dict[str, Any] = []
    downloaded_at: Any  # datetime | None
    tokens_consumed: int
    file_size_bytes: int
    copy_exists: bool


class MyDownloadsResponse(BaseModel):
    items: list[MyDownloadItem]
    storage_used_bytes: int


@router.get("/downloads/copy-file")
def download_copy_file(
    audio_id: str = Query(...),
    user_id: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        verify_copy_download(audio_id, user_id, exp, sig)
    except SignedURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": exc.message},
        )

    try:
        parsed_audio_id = uuid.UUID(audio_id)
        parsed_user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})

    copy_path = audio_file.get_copy_path(parsed_user_id, parsed_audio_id)
    if not copy_path.exists():
        # Fallback: serve original
        audio = db.execute(select(Audio).where(Audio.id == parsed_audio_id)).scalar_one_or_none()
        if audio is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})
        orig_path = Path(audio.file_path)
        if not orig_path.exists():
            raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "file missing"})
        title = audio.title
        return FileResponse(path=str(orig_path), media_type="audio/wav", filename=f"{title}.wav")

    audio = db.execute(select(Audio).where(Audio.id == parsed_audio_id)).scalar_one_or_none()
    title = audio.title if audio else audio_id
    return FileResponse(path=str(copy_path), media_type="audio/wav", filename=f"{title}.wav")


@router.get("/downloads", response_model=MyDownloadsResponse)
def list_my_downloads(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> MyDownloadsResponse:
    from sqlalchemy.orm import joinedload

    audios = db.execute(
        select(Audio)
        .options(joinedload(Audio.creator), joinedload(Audio.tags))
        .where(Audio.downloaded_by_user_id == current_user.id)
        .order_by(Audio.downloaded_at.desc())
    ).unique().scalars().all()

    audio_ids = [a.id for a in audios]

    # tokens consumed per audio
    token_rows = db.execute(
        select(TokenConsumption.audio_id, TokenConsumption.tokens)
        .where(
            TokenConsumption.user_id == current_user.id,
            TokenConsumption.audio_id.in_(audio_ids),
        )
    ).all()
    tokens_map: dict[uuid.UUID, int] = {r.audio_id: r.tokens for r in token_rows}

    items: list[MyDownloadItem] = []
    storage_used = 0

    for audio in audios:
        copy_path = audio_file.get_copy_path(current_user.id, audio.id)
        copy_exists = copy_path.exists()
        file_size = copy_path.stat().st_size if copy_exists else 0
        storage_used += file_size

        items.append(MyDownloadItem(
            id=str(audio.id),
            title=audio.title,
            creator=CreatorBrief(
                id=str(audio.creator.user_id),
                display_name=audio.creator.display_name,
            ),
            duration_sec=audio.duration_sec,
            token_cost=audio.duration_sec,
            tags=[t.name for t in audio.tags],
            peaks=audio.peaks,
            downloaded_at=audio.downloaded_at,
            tokens_consumed=tokens_map.get(audio.id, 0),
            file_size_bytes=file_size,
            copy_exists=copy_exists,
        ))

    return MyDownloadsResponse(items=items, storage_used_bytes=storage_used)


@router.get("/downloads/{audio_id}/copy-url")
def get_copy_url(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})

    audio = db.execute(
        select(Audio).where(Audio.id == parsed_id)
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    if audio.downloaded_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "not your audio"},
        )

    # Log re-download
    db.add(DownloadLog(
        user_id=current_user.id,
        audio_id=parsed_id,
        kind=DownloadKind.redownload,
    ))
    db.commit()

    params = issue_copy_download(audio_id, str(current_user.id))
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": f"/api/v1/me/downloads/copy-file?{qs}"}


@router.delete("/downloads/{audio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_download(
    audio_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    try:
        parsed_id = uuid.UUID(audio_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})

    audio = db.execute(
        select(Audio.downloaded_by_user_id).where(Audio.id == parsed_id)
    ).scalar_one_or_none()
    if audio is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "audio not found"})

    if audio != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "not your audio"},
        )

    copy_path = audio_file.get_copy_path(current_user.id, parsed_id)
    if copy_path.exists():
        copy_path.unlink(missing_ok=True)


# ─── Session ping (改訂2) ─────────────────────────────────────────────────────

@router.post("/session/ping")
def session_ping(
    response: Response,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict:
    """フロントが主要ページに到達した時に1回叩く。
    直近 30分以内に同ユーザの session 記録があれば 204、なければ INSERT して 201。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=SESSION_DEDUP_WINDOW_SEC)
    recent = db.execute(
        select(ActivityLog.id)
        .where(
            ActivityLog.user_id == current_user.id,
            ActivityLog.kind == ActivityKind.session,
            ActivityLog.created_at >= cutoff,
        )
        .limit(1)
    ).scalar_one_or_none()
    if recent is not None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return {}
    db.add(ActivityLog(user_id=current_user.id, kind=ActivityKind.session))
    db.commit()
    response.status_code = status.HTTP_201_CREATED
    return {"recorded": True}
